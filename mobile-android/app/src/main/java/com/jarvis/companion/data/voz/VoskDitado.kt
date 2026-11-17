package com.jarvis.companion.data.voz

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer

/**
 * Reconhecimento de voz offline com Vosk.
 *
 * Fluxo tipico:
 *  1. ModeloVosk.baixarSePreciso() (uma vez).
 *  2. VoskDitado(ctx).iniciar() — comeca a ouvir o microfone (PCM 16k mono).
 *  3. collect no [parcial] enquanto fala.
 *  4. parar() devolve o texto final e libera o AudioRecord + Model.
 *
 * Todo o trabalho e feito na thread do coroutine que chamar — use um
 * Dispatchers.IO ou Default no viewModel.
 */
class VoskDitado(private val ctx: Context) {

    companion object { const val SAMPLE_RATE = 16000 }

    private var model: Model? = null
    private var reconhecedor: Recognizer? = null
    private var gravador: AudioRecord? = null
    private var rodando = false

    private val _parcial = MutableStateFlow("")
    val parcial: StateFlow<String> = _parcial.asStateFlow()

    private val _finalizado = MutableStateFlow("")
    val finalizado: StateFlow<String> = _finalizado.asStateFlow()

    @SuppressLint("MissingPermission")
    suspend fun iniciar(caminhoModelo: String) = withContext(Dispatchers.IO) {
        if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            throw SecurityException("Permissao RECORD_AUDIO negada.")
        }
        model = Model(caminhoModelo)
        reconhecedor = Recognizer(model, SAMPLE_RATE.toFloat())
        val bufMin = AudioRecord.getMinBufferSize(SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val buf = (bufMin * 4).coerceAtLeast(SAMPLE_RATE / 2)
        gravador = AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, buf)
        gravador?.startRecording()
        rodando = true
        val chunk = ByteArray(buf)
        while (rodando) {
            val n = gravador?.read(chunk, 0, chunk.size) ?: 0
            if (n <= 0) continue
            val completo = reconhecedor?.acceptWaveForm(chunk, n) ?: false
            if (completo) {
                val txt = JSONObject(reconhecedor!!.result).optString("text", "").trim()
                if (txt.isNotBlank()) {
                    _finalizado.value = (_finalizado.value + " " + txt).trim()
                    _parcial.value = ""
                }
            } else {
                val txt = JSONObject(reconhecedor!!.partialResult).optString("partial", "").trim()
                _parcial.value = txt
            }
        }
    }

    suspend fun parar(): String = withContext(Dispatchers.IO) {
        rodando = false
        try { gravador?.stop() } catch (_: Throwable) {}
        gravador?.release()
        gravador = null
        val restante = try { JSONObject(reconhecedor!!.finalResult).optString("text", "") } catch (_: Throwable) { "" }
        if (restante.isNotBlank()) {
            _finalizado.value = (_finalizado.value + " " + restante).trim()
        }
        try { reconhecedor?.close() } catch (_: Throwable) {}
        try { model?.close() } catch (_: Throwable) {}
        reconhecedor = null
        model = null
        _parcial.value = ""
        val saida = _finalizado.value
        saida
    }

    fun limpar() {
        _finalizado.value = ""
        _parcial.value = ""
    }
}
