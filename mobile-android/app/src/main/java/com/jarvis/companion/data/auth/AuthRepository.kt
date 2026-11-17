package com.jarvis.companion.data.auth

import com.jarvis.companion.data.network.JarvisApi
import com.jarvis.companion.data.network.LoginOutcome
import com.jarvis.companion.data.network.PersistentCookieJar
import com.jarvis.companion.data.settings.SettingsStore
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * O "estou autenticado?" do app: ou tem cookie salvo, ou ainda vai pedir
 * senha. Nunca guardamos a senha; o cookie faz a sessão.
 */
class AuthRepository(
    private val api: JarvisApi,
    private val settings: SettingsStore,
    private val cookies: PersistentCookieJar,
) {
    private val _estado = MutableStateFlow(estadoAtual())
    val estado: StateFlow<AuthEstado> = _estado.asStateFlow()

    suspend fun entrar(senha: String): LoginOutcome {
        val resposta = api.login(senha)
        if (resposta is LoginOutcome.Ok) _estado.value = AuthEstado.Autenticado
        return resposta
    }

    fun sair() {
        cookies.limpar()
        _estado.value = AuthEstado.Deslogado
    }

    fun revalidar() { _estado.value = estadoAtual() }

    private fun estadoAtual(): AuthEstado =
        if (settings.readCookies().isNotBlank()) AuthEstado.Autenticado else AuthEstado.Deslogado
}

enum class AuthEstado { Autenticado, Deslogado }
