package com.jarvis.companion.data.network

import com.jarvis.companion.data.settings.SettingsStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.encodeToString
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * Cliente das rotas REST do JARVIS. Fino de propósito: cada método faz UM
 * pedido, devolve o corpo bruto ou lança [ApiException]. Quem decide o que
 * fazer com o erro (reautenticar, avisar o usuário, ignorar) é o chamador.
 */
class JarvisApi(
    private val client: OkHttpClient,
    private val settings: SettingsStore,
) {
    private val jsonType = "application/json; charset=utf-8".toMediaType()

    private fun url(caminho: String): String {
        val base = settings.current().baseUrl
        require(base.isNotBlank()) { "endereço do JARVIS ainda não configurado" }
        return base + caminho
    }

    /** Ping: só valida que tem alguém ouvindo. Nunca lança por 4xx/5xx. */
    suspend fun saude(): Boolean = withContext(Dispatchers.IO) {
        runCatching {
            client.newCall(Request.Builder().url(url("/api/saude")).build())
                .execute().use { it.isSuccessful }
        }.getOrDefault(false)
    }

    suspend fun login(senha: String): LoginOutcome = withContext(Dispatchers.IO) {
        val corpo = jarvisJson.encodeToString(LoginRequest(senha)).toRequestBody(jsonType)
        val pedido = Request.Builder().url(url("/login")).post(corpo).build()
        client.newCall(pedido).execute().use { r ->
            when (r.code) {
                200 -> LoginOutcome.Ok
                401 -> LoginOutcome.SenhaErrada
                503 -> LoginOutcome.SemSenha
                else -> LoginOutcome.Erro("HTTP ${r.code}")
            }
        }
    }

    suspend fun estado(): Retrato = withContext(Dispatchers.IO) {
        val pedido = Request.Builder().url(url("/api/estado")).build()
        client.newCall(pedido).execute().use { r ->
            if (!r.isSuccessful) throw ApiException(r.code, "estado: HTTP ${r.code}")
            val texto = r.body?.string().orEmpty()
            jarvisJson.decodeFromString(Retrato.serializer(), texto)
        }
    }

    suspend fun comando(texto: String) = withContext(Dispatchers.IO) {
        val corpo = jarvisJson.encodeToString(ComandoRequest(texto)).toRequestBody(jsonType)
        exec("POST", "/api/comando", corpo)
    }

    suspend fun escutar() = withContext(Dispatchers.IO) { exec("POST", "/api/escutar", null) }
    suspend fun cancelar() = withContext(Dispatchers.IO) { exec("POST", "/api/cancelar", null) }

    suspend fun presenca(carga: PresencaRequest) = withContext(Dispatchers.IO) {
        val corpo = jarvisJson.encodeToString(PresencaRequest.serializer(), carga).toRequestBody(jsonType)
        exec("POST", "/api/presenca", corpo)
    }

    private fun exec(metodo: String, caminho: String,
                     corpo: okhttp3.RequestBody?): String {
        val b = Request.Builder().url(url(caminho))
        when (metodo) {
            "POST" -> b.post(corpo ?: "".toRequestBody(jsonType))
            "GET" -> b.get()
        }
        return client.newCall(b.build()).execute().use { r ->
            if (!r.isSuccessful) throw ApiException(r.code, "$caminho: HTTP ${r.code}")
            r.body?.string().orEmpty()
        }
    }
}

sealed interface LoginOutcome {
    data object Ok : LoginOutcome
    data object SenhaErrada : LoginOutcome
    data object SemSenha : LoginOutcome
    data class Erro(val mensagem: String) : LoginOutcome
}

class ApiException(val code: Int, mensagem: String) : RuntimeException(mensagem)
