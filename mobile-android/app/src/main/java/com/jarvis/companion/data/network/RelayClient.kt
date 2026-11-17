package com.jarvis.companion.data.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.MediaType.Companion.toMediaType
import org.json.JSONObject

/**
 * Cliente de relé HTTPS (rotas em /jarvis/ no domínio configurado). Usado quando o
 * celular NÃO está na mesma rede do PC (4G, Wi-Fi externo). Enfileira o pedido
 * de wake num servidor público; a ESP32 lá em casa, que fica sempre on,
 * puxa o pedido e dispara o pacote mágico na LAN.
 *
 * O token é compartilhado entre: este app, as rotas PHP e a ESP32. Nunca
 * entra em log nem na UI.
 */
class RelayClient(private val client: OkHttpClient) {

    enum class Resultado { OK, SemRede, Negado }

    /** Enfileira um wake no relé. Devolve OK quando o servidor confirmou. */
    suspend fun acordarRemoto(): Resultado = withContext(Dispatchers.IO) {
        val corpo = JSONObject().put("token", TOKEN).toString()
            .toRequestBody("application/json".toMediaType())
        val pedido = Request.Builder().url(URL_WAKE).post(corpo).build()
        runCatching {
            client.newCall(pedido).execute().use { r ->
                when {
                    r.code == 200 -> Resultado.OK
                    r.code in listOf(401, 403) -> Resultado.Negado
                    else -> Resultado.SemRede
                }
            }
        }.getOrDefault(Resultado.SemRede)
    }

    /** Pergunta ao relé se o PC já sinalizou vida recente (heartbeat). */
    suspend fun pcEstaOnline(): Boolean = withContext(Dispatchers.IO) {
        val pedido = Request.Builder().url("$URL_STATUS?token=$TOKEN").get().build()
        runCatching {
            client.newCall(pedido).execute().use { r ->
                if (r.code != 200) return@use false
                val corpo = r.body?.string().orEmpty()
                JSONObject(corpo).optBoolean("online", false)
            }
        }.getOrDefault(false)
    }

    companion object {
        private const val URL_WAKE = "https://seu-dominio.example/jarvis/wake"
        private const val URL_STATUS = "https://seu-dominio.example/jarvis/status"
        // Deixe exatamente igual ao token nos PHPs e no jarvis_relay.py.
        private const val TOKEN = "p0kCRE3hf8oJ4qOexNt7s2IFYAVylBgc"
    }
}
