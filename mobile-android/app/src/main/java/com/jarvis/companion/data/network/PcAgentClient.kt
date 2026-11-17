package com.jarvis.companion.data.network

import com.jarvis.companion.data.settings.SettingsStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * Cliente do pc_agent que roda no PC (porta 8765). Faz uma unica coisa:
 * pedir que o PC inicie o processo `python -m jarvis --servidor` caso
 * ele tenha caido. Usa o mesmo token que a placa ESP32 usa, guardado
 * cifrado via Keystore em [SettingsStore].
 *
 * O token NAO e exibido em UI, nunca entra em log, nunca sai do aparelho
 * exceto como `Authorization: Bearer <token>` para o pc_agent da rede
 * local do usuario.
 */
class PcAgentClient(
    private val client: OkHttpClient,
    private val settings: SettingsStore,
) {
    enum class Resultado { JaRodando, Iniciando, Parado, Suspendendo, Desligando,
                           SemToken, SemAgente, Erro }

    suspend fun iniciarJarvis() = chamar("/start_jarvis", "START")
    suspend fun pararJarvis() = chamar("/stop_jarvis", "STOP")
    suspend fun suspenderPc() = chamar("/sleep", "SLEEP")
    suspend fun desligarPc() = chamar("/shutdown", "SHUTDOWN")
    suspend fun cancelarDesligamento() = chamar("/cancel", "CANCEL")

    private suspend fun chamar(rota: String, confirm: String): Resultado =
        withContext(Dispatchers.IO) {
            val token = settings.readAgentToken().trim()
            if (token.isEmpty()) return@withContext Resultado.SemToken
            val alvo = hostDoAgente() ?: return@withContext Resultado.SemAgente
            val pedido = Request.Builder()
                .url("$alvo$rota")
                .post("confirm=$confirm".toRequestBody(FORM))
                .header("Authorization", "Bearer $token")
                .build()
            runCatching {
                client.newCall(pedido).execute().use { r ->
                    when {
                        r.code == 200 && rota == "/start_jarvis" -> Resultado.JaRodando
                        r.code == 200 && rota == "/stop_jarvis" -> Resultado.Parado
                        r.code == 202 && rota == "/start_jarvis" -> Resultado.Iniciando
                        r.code == 202 && rota == "/stop_jarvis" -> Resultado.Parado
                        r.code == 202 && rota == "/sleep" -> Resultado.Suspendendo
                        r.code == 202 && rota == "/shutdown" -> Resultado.Desligando
                        r.code in listOf(401, 403) -> Resultado.SemToken
                        else -> Resultado.Erro
                    }
                }
            }.getOrDefault(Resultado.SemAgente)
        }

    /** Deriva "http://IP:8765" a partir do baseUrl atual do JARVIS. */
    private fun hostDoAgente(): String? {
        val base = settings.current().baseUrl
        if (base.isBlank()) return null
        val sem = base.removeSuffix("/")
        // troca a porta (padrao 8080) por 8765
        val semPorta = sem.replace(Regex(":\\d+$"), "")
        return "$semPorta:8765"
    }

    companion object {
        private val FORM = "application/x-www-form-urlencoded".toMediaType()
    }
}
