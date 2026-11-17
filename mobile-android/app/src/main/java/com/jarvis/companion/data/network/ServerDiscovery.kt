package com.jarvis.companion.data.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

/**
 * Descoberta automática do servidor JARVIS. Tenta cada endereço candidato
 * em paralelo, retorna o primeiro que responder 200 no `/api/saude` dentro
 * do tempo limite. Sem mDNS/broadcast: a lista de candidatos é fixa, vem
 * dos endereços conhecidos deste usuário (LAN + Tailscale), por simplicidade
 * e porque mDNS no Android exige permissões e serviço zeroconf no PC.
 *
 * Nada aqui grava em disco ou loga; quem decide o que fazer com o resultado
 * é o chamador (normalmente o AppNav na primeira abertura).
 */
class ServerDiscovery(private val base: OkHttpClient) {

    private val sondagem: OkHttpClient by lazy {
        base.newBuilder()
            .connectTimeout(1500, TimeUnit.MILLISECONDS)
            .readTimeout(1500, TimeUnit.MILLISECONDS)
            .callTimeout(2000, TimeUnit.MILLISECONDS)
            .build()
    }

    /**
     * @return a primeira URL base que respondeu, ou `null` se nenhum
     *         candidato respondeu dentro de [tempoMaxMs].
     */
    suspend fun descobrir(
        candidatos: List<String> = PADROES,
        tempoMaxMs: Long = 3_000L,
    ): String? = withContext(Dispatchers.IO) {
        if (candidatos.isEmpty()) return@withContext null
        withTimeoutOrNull(tempoMaxMs) {
            coroutineScope {
                candidatos
                    .map { url -> async { if (pingar(url)) url else null } }
                    .awaitAll()
                    .firstOrNull { it != null }
            }
        }
    }

    private fun pingar(baseUrl: String): Boolean = runCatching {
        val pedido = Request.Builder().url("$baseUrl/api/saude").get().build()
        sondagem.newCall(pedido).execute().use { it.isSuccessful }
    }.getOrDefault(false)

    companion object {
        /** Endereços conhecidos deste usuário: LAN primeiro, Tailscale depois. */
        val PADROES: List<String> = listOf(
            "http://192.168.50.10:8080",
            "https://seu-servidor-tailscale:8080",
        )
    }
}
