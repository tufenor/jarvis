package com.jarvis.companion.data.settings

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Preferências guardadas com chave mestre do Android Keystore. O arquivo em
 * disco é cifrado; a chave não deixa o TEE/Keystore. Mantém URL, nome do
 * aparelho, modo econômico e os cookies de sessão.
 *
 * Não loga nem expõe o conteúdo. `SettingsStore` é a única rota de leitura
 * e escrita para o resto do app.
 */
class SettingsStore internal constructor(private val prefs: SharedPreferences) {

    private val _state = MutableStateFlow(snapshot())
    val state: StateFlow<Settings> = _state.asStateFlow()

    fun current(): Settings = _state.value

    fun updateBaseUrl(url: String) = edit { putString(KEY_URL, normalize(url)) }
    fun updateDeviceName(name: String) = edit { putString(KEY_DEVICE, name.trim().ifBlank { "a53" }) }
    fun updateBatterySaver(on: Boolean) = edit { putBoolean(KEY_SAVER, on) }
    fun updateOperatorName(name: String) = edit {
        putString(KEY_OPERATOR, name.trim().ifBlank { "SENHOR" })
    }

    internal fun storeCookies(value: String) = edit { putString(KEY_COOKIES, value) }
    internal fun readCookies(): String = prefs.getString(KEY_COOKIES, "") ?: ""
    internal fun clearCookies() = edit { remove(KEY_COOKIES) }

    fun updateAgentToken(token: String) = edit { putString(KEY_AGENT_TOKEN, token.trim()) }
    fun readAgentToken(): String = prefs.getString(KEY_AGENT_TOKEN, "") ?: ""

    private inline fun edit(block: SharedPreferences.Editor.() -> Unit) {
        prefs.edit().apply(block).apply()
        _state.value = snapshot()
    }

    private fun snapshot() = Settings(
        baseUrl = prefs.getString(KEY_URL, "") ?: "",
        deviceName = prefs.getString(KEY_DEVICE, "a53") ?: "a53",
        batterySaver = prefs.getBoolean(KEY_SAVER, false),
        operatorName = prefs.getString(KEY_OPERATOR, "SENHOR") ?: "SENHOR",
    )

    companion object {
        private const val FILE = "jarvis_companion_secure"
        private const val KEY_URL = "base_url"
        private const val KEY_DEVICE = "device_name"
        private const val KEY_SAVER = "battery_saver"
        private const val KEY_COOKIES = "cookies"
        private const val KEY_AGENT_TOKEN = "agent_token"
        private const val KEY_OPERATOR = "operator_name"

        fun create(context: Context): SettingsStore {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()
            val prefs = EncryptedSharedPreferences.create(
                context, FILE, masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            )
            return SettingsStore(prefs)
        }

        /** Para testes JVM: SettingsStore sobre qualquer SharedPreferences (ex.: in-memory). */
        fun forTesting(prefs: SharedPreferences): SettingsStore = SettingsStore(prefs)

        internal fun normalize(url: String): String {
            val trimmed = url.trim().trimEnd('/')
            if (trimmed.isEmpty()) return ""
            return if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) trimmed
            else "http://$trimmed"
        }
    }
}

data class Settings(
    val baseUrl: String,
    val deviceName: String,
    val batterySaver: Boolean,
    val operatorName: String = "SENHOR",
)
