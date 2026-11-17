package com.jarvis.companion.data.network

import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

/**
 * Único cliente HTTP do app (OkHttp já faz pool de conexões por host). O
 * CookieJar entra aqui para que requisições REST e o WebSocket compartilhem
 * a mesma sessão. TLS fica no padrão da plataforma — nunca desativamos
 * verificação de certificado.
 */
object HttpClientFactory {
    fun create(cookies: PersistentCookieJar): OkHttpClient = OkHttpClient.Builder()
        .cookieJar(cookies)
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .callTimeout(60, TimeUnit.SECONDS)
        .pingInterval(25, TimeUnit.SECONDS)   // mantém o WS vivo por NATs
        .retryOnConnectionFailure(true)
        .build()
}
