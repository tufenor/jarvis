package com.jarvis.companion.data.voz

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.speech.tts.Voice
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.Locale

/**
 * Microfone e voz do celular. Encapsula [SpeechRecognizer] (fala → texto)
 * e [TextToSpeech] (texto → fala) do Android. Nenhum áudio ou texto deixa
 * o aparelho por aqui: o reconhecimento vai pro serviço de voz padrão do
 * Android (Google) e a sintese roda local.
 *
 * O ciclo de vida é colado ao processo do app: instancia uma vez via
 * Services, chama [desligar] antes de sumir.
 */
class VozMovel(context: Context) {

    enum class Estado { Repouso, Ouvindo, Processando, Falando, SemSuporte, SemPermissao }

    private val _estado = MutableStateFlow(Estado.Repouso)
    val estado: StateFlow<Estado> = _estado.asStateFlow()

    private val _parcial = MutableStateFlow("")
    val parcial: StateFlow<String> = _parcial.asStateFlow()

    private var tts: TextToSpeech? = null
    private var reconhecedor: SpeechRecognizer? = null
    private val ctx = context.applicationContext

    private var aoReconhecer: ((String) -> Unit)? = null
    private var aoFalarTerminado: (() -> Unit)? = null

    init {
        // Prefere o motor da Google (vozes neurais em pt-BR). Se nao estiver
        // instalado, cai para o motor padrao.
        val motorPreferido = "com.google.android.tts"
        val onInit = TextToSpeech.OnInitListener { status ->
            if (status != TextToSpeech.SUCCESS) return@OnInitListener
            tts?.language = Locale("pt", "BR")
            tts?.setSpeechRate(1.0f)
            tts?.setPitch(0.95f)
            escolherMelhorVoz(tts)
        }
        tts = runCatching {
            TextToSpeech(ctx, onInit, motorPreferido)
        }.getOrElse { TextToSpeech(ctx, onInit) }
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) { _estado.value = Estado.Falando }
            override fun onDone(utteranceId: String?) {
                _estado.value = Estado.Repouso
                aoFalarTerminado?.invoke()
            }
            @Deprecated("API antiga")
            override fun onError(utteranceId: String?) { _estado.value = Estado.Repouso }
        })
    }

    /** Começa a ouvir. Chame [aoFim] com o texto final; `null` se ninguém falou. */
    fun ouvir(aoFim: (String?) -> Unit) {
        if (!SpeechRecognizer.isRecognitionAvailable(ctx)) {
            _estado.value = Estado.SemSuporte
            aoFim(null); return
        }
        pararReconhecedor()
        aoReconhecer = { texto ->
            aoReconhecer = null
            if (texto.isBlank()) aoFim(null) else aoFim(texto)
        }
        _parcial.value = ""
        _estado.value = Estado.Ouvindo
        reconhecedor = SpeechRecognizer.createSpeechRecognizer(ctx).apply {
            setRecognitionListener(ouvinte)
            startListening(intentFala())
        }
    }

    /** Fala e, quando terminar, chama [aoTerminar] (útil para re-escutar em loop). */
    fun falar(texto: String, aoTerminar: (() -> Unit)? = null) {
        if (texto.isBlank()) { aoTerminar?.invoke(); return }
        aoFalarTerminado = aoTerminar
        _estado.value = Estado.Falando
        val id = texto.hashCode().toString()
        val params = Bundle().apply {
            putString(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, id)
        }
        tts?.speak(texto, TextToSpeech.QUEUE_FLUSH, params, id)
    }

    fun pararTudo() {
        pararReconhecedor()
        tts?.stop()
        _estado.value = Estado.Repouso
    }

    fun desligar() {
        pararReconhecedor()
        tts?.stop()
        tts?.shutdown()
        tts = null
    }

    /**
     * Varre as vozes instaladas e escolhe a de melhor qualidade em pt-BR.
     * Prefere: QUALITY_VERY_HIGH ou QUALITY_HIGH, feminina se houver, e
     * evita vozes marcadas como `NOT_INSTALLED` ou que exigem internet.
     */
    private fun escolherMelhorVoz(engine: TextToSpeech?) {
        val tts = engine ?: return
        val vozes = runCatching { tts.voices }.getOrNull().orEmpty()
        val candidatas = vozes.filter {
            it.locale.language == "pt" && it.locale.country == "BR"
                    && "notInstalled" !in (it.features ?: emptySet())
        }
        if (candidatas.isEmpty()) return
        val melhor = candidatas.maxByOrNull { v ->
            var pontos = 0
            pontos += when (v.quality) {
                Voice.QUALITY_VERY_HIGH -> 400
                Voice.QUALITY_HIGH -> 300
                Voice.QUALITY_NORMAL -> 200
                Voice.QUALITY_LOW -> 100
                else -> 0
            }
            // Vozes neurais da Google geralmente contem "network", "neural" ou "wavenet".
            val nome = v.name.lowercase()
            if ("neural" in nome || "wavenet" in nome) pontos += 80
            if ("network" in nome) pontos += 40
            // Preferencia leve por feminina (corresponde ao padrao faber/cadu).
            if ("female" in nome || nome.endsWith("f")) pontos += 10
            pontos
        }
        melhor?.let { tts.voice = it }
    }

    private fun pararReconhecedor() {
        try { reconhecedor?.cancel() } catch (_: Exception) {}
        try { reconhecedor?.destroy() } catch (_: Exception) {}
        reconhecedor = null
    }

    private fun intentFala() = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                 RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        putExtra(RecognizerIntent.EXTRA_LANGUAGE, "pt-BR")
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "pt-BR")
        putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, false)
        putExtra("android.speech.extra.DICTATION_MODE", true)
    }

    private val ouvinte = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) { _estado.value = Estado.Ouvindo }
        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(rms: Float) {}
        override fun onBufferReceived(buffer: ByteArray?) {}
        override fun onEndOfSpeech() { _estado.value = Estado.Processando }
        override fun onError(error: Int) {
            _estado.value = when (error) {
                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> Estado.SemPermissao
                else -> Estado.Repouso
            }
            aoReconhecer?.invoke("")
            aoReconhecer = null
        }
        override fun onResults(results: Bundle?) {
            val texto = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull()?.trim().orEmpty()
            _parcial.value = texto
            _estado.value = Estado.Repouso
            aoReconhecer?.invoke(texto)
            aoReconhecer = null
        }
        override fun onPartialResults(results: Bundle?) {
            val texto = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull()?.trim().orEmpty()
            if (texto.isNotEmpty()) _parcial.value = texto
        }
        override fun onEvent(eventType: Int, params: Bundle?) {}
    }
}
