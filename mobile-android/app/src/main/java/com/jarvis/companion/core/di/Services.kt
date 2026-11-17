package com.jarvis.companion.core.di

import android.content.Context
import com.jarvis.companion.data.auth.AuthRepository
import com.jarvis.companion.data.network.HttpClientFactory
import com.jarvis.companion.BuildConfig
import com.jarvis.companion.data.network.JarvisApi
import com.jarvis.companion.data.network.PcAgentClient
import com.jarvis.companion.data.network.PersistentCookieJar
import com.jarvis.companion.data.network.RelayClient
import com.jarvis.companion.data.network.ServerDiscovery
import com.jarvis.companion.data.network.StateChannel
import com.jarvis.companion.data.voz.VozMovel
import com.jarvis.companion.data.presence.PresenceReporter
import com.jarvis.companion.data.settings.SettingsStore

/**
 * Service locator leve. Hilt seria exagero para um app de poucas telas e
 * dificulta o build sem internet. Tudo que precisa viver pelo processo
 * mora aqui, construído uma única vez.
 */
class Services internal constructor(
    val settings: SettingsStore,
    val cookies: PersistentCookieJar,
    val api: JarvisApi,
    val auth: AuthRepository,
    val channel: StateChannel,
    val presence: PresenceReporter,
    val discovery: ServerDiscovery,
    val pcAgent: PcAgentClient,
    val voz: VozMovel,
    val rele: RelayClient,
) {
    companion object {
        fun build(context: Context): Services {
            val app = context.applicationContext
            val settings = SettingsStore.create(app)
            // Semeia o token do pc_agent uma vez, se ja veio embutido no APK
            // e o Keystore ainda nao tem nada.
            if (settings.readAgentToken().isBlank() && BuildConfig.PC_AGENT_TOKEN.isNotBlank()) {
                settings.updateAgentToken(BuildConfig.PC_AGENT_TOKEN)
            }
            val cookies = PersistentCookieJar(settings)
            val client = HttpClientFactory.create(cookies)
            val api = JarvisApi(client, settings)
            val auth = AuthRepository(api, settings, cookies)
            val channel = StateChannel(client, settings)
            val presence = PresenceReporter(app, api, settings)
            val discovery = ServerDiscovery(client)
            val pcAgent = PcAgentClient(client, settings)
            val voz = VozMovel(app)
            val rele = RelayClient(client)
            return Services(settings, cookies, api, auth, channel, presence, discovery, pcAgent, voz, rele)
        }
    }
}
