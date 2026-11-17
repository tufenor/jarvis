package com.jarvis.companion.data.network

import com.jarvis.companion.data.settings.SettingsStore
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl

/**
 * CookieJar simples sobre o SettingsStore cifrado. O JARVIS só precisa de um
 * cookie (o `jarvis_sessao`); guardar como "nome=valor; nome=valor" dá e sobra.
 * Qualquer cookie expirado some em memória sem precisar reescrever o disco.
 */
class PersistentCookieJar(private val settings: SettingsStore) : CookieJar {

    private val memoria = mutableMapOf<String, MutableList<Cookie>>()

    init { carregar() }

    @Synchronized
    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        if (cookies.isEmpty()) return
        val host = url.host
        val atuais = memoria.getOrPut(host) { mutableListOf() }
        for (novo in cookies) {
            atuais.removeAll { it.name == novo.name && it.domain == novo.domain }
            if (!novo.expiresAt.let { it in 1..System.currentTimeMillis() }) {
                atuais.add(novo)
            }
        }
        persistir()
    }

    @Synchronized
    override fun loadForRequest(url: HttpUrl): List<Cookie> {
        val agora = System.currentTimeMillis()
        val lista = memoria[url.host] ?: return emptyList()
        val ativos = lista.filter { it.expiresAt > agora }
        if (ativos.size != lista.size) {
            memoria[url.host] = ativos.toMutableList()
            persistir()
        }
        return ativos
    }

    @Synchronized
    fun limpar() {
        memoria.clear()
        settings.clearCookies()
    }

    private fun persistir() {
        val serial = buildString {
            memoria.values.forEach { lista ->
                lista.forEach { c ->
                    append(c.toString()); append("||"); append(c.domain); append("\n")
                }
            }
        }
        settings.storeCookies(serial)
    }

    private fun carregar() {
        val texto = settings.readCookies()
        if (texto.isBlank()) return
        for (linha in texto.lines()) {
            if (linha.isBlank()) continue
            val (bruto, host) = linha.split("||", limit = 2).let {
                it[0] to it.getOrNull(1).orEmpty()
            }
            if (host.isBlank()) continue
            val url = HttpUrl.Builder().scheme("https").host(host).build()
            val cookie = Cookie.parse(url, bruto) ?: continue
            memoria.getOrPut(host) { mutableListOf() }.add(cookie)
        }
    }
}
