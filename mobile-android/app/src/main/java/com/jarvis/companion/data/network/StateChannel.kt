package com.jarvis.companion.data.network

import com.jarvis.companion.data.settings.SettingsStore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import kotlin.math.min

/**
 * WebSocket resiliente. Backoff exponencial com teto, nunca abre duas
 * conexões ao mesmo tempo — usar `conectar()` quando já conectado reusa
 * o canal. `desconectar()` é idempotente.
 */
class StateChannel(
    private val client: OkHttpClient,
    private val settings: SettingsStore,
) {
    private val escopo = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var jobAtual: Job? = null
    private var ws: WebSocket? = null

    private val _conexao = MutableStateFlow<ConexaoCanal>(ConexaoCanal.Offline)
    val conexao: StateFlow<ConexaoCanal> = _conexao.asStateFlow()

    private val _ultimo = MutableStateFlow<Retrato?>(null)
    val ultimo: StateFlow<Retrato?> = _ultimo.asStateFlow()

    fun conectar() {
        if (jobAtual?.isActive == true) return
        jobAtual = escopo.launch {
            var tentativa = 0
            while (true) {
                val base = settings.current().baseUrl
                if (base.isBlank()) {
                    _conexao.value = ConexaoCanal.AguardandoConfig
                    delay(2_000)
                    continue
                }
                _conexao.value = if (tentativa == 0) ConexaoCanal.Conectando else ConexaoCanal.Reconectando
                val sucesso = abrirUmaVez(wsUrlDe(base))
                if (sucesso) {
                    tentativa = 0
                } else {
                    tentativa++
                    val atraso = min(30_000L, 500L * (1L shl min(tentativa, 6)))
                    delay(atraso)
                }
            }
        }
    }

    fun desconectar() {
        jobAtual?.cancel()
        jobAtual = null
        ws?.cancel()
        ws = null
        _conexao.value = ConexaoCanal.Offline
    }

    private suspend fun abrirUmaVez(url: String): Boolean {
        val pedido = Request.Builder().url(url).build()
        val resultado = MutableStateFlow<Boolean?>(null)
        val socket = client.newWebSocket(pedido, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                _conexao.value = ConexaoCanal.Online
                resultado.value = true
            }
            override fun onMessage(webSocket: WebSocket, text: String) {
                runCatching { jarvisJson.decodeFromString(Retrato.serializer(), text) }
                    .onSuccess { _ultimo.value = it }
            }
            override fun onMessage(webSocket: WebSocket, bytes: ByteString) { /* ignora */ }
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(1000, null); resultado.value = false
            }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                _conexao.value = when (response?.code) {
                    401 -> ConexaoCanal.AguardandoAuth
                    else -> ConexaoCanal.Erro(t.message ?: "falha")
                }
                resultado.value = false
            }
        })
        ws = socket
        // Espera a resposta inicial (open ou falha) para medir atraso.
        while (resultado.value == null) delay(50)
        return resultado.value == true
    }

    private fun wsUrlDe(base: String): String {
        val limpo = base.removeSuffix("/")
        return when {
            limpo.startsWith("https://") -> "wss://" + limpo.removePrefix("https://") + "/ws"
            limpo.startsWith("http://") -> "ws://" + limpo.removePrefix("http://") + "/ws"
            else -> "ws://$limpo/ws"
        }
    }
}

sealed interface ConexaoCanal {
    data object Offline : ConexaoCanal
    data object Conectando : ConexaoCanal
    data object Reconectando : ConexaoCanal
    data object AguardandoConfig : ConexaoCanal
    data object AguardandoAuth : ConexaoCanal
    data object Online : ConexaoCanal
    data class Erro(val mensagem: String) : ConexaoCanal
}
