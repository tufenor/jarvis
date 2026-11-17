package com.jarvis.companion

import com.jarvis.companion.data.network.PersistentCookieJar
import com.jarvis.companion.data.settings.SettingsStore
import okhttp3.Cookie
import okhttp3.HttpUrl.Companion.toHttpUrl
import org.junit.Assert.assertEquals
import org.junit.Test

class CookieJarTest {
    /** Teste JVM — simula o SharedPreferences por um dicionário em memória. */
    private fun criarStore(): SettingsStore {
        val mem = mutableMapOf<String, Any?>()
        val prefs = object : android.content.SharedPreferences {
            override fun getAll() = mem.toMap()
            override fun getString(k: String?, d: String?) = mem[k] as? String ?: d
            override fun getStringSet(k: String?, d: MutableSet<String>?) = d
            override fun getInt(k: String?, d: Int) = (mem[k] as? Int) ?: d
            override fun getLong(k: String?, d: Long) = (mem[k] as? Long) ?: d
            override fun getFloat(k: String?, d: Float) = (mem[k] as? Float) ?: d
            override fun getBoolean(k: String?, d: Boolean) = (mem[k] as? Boolean) ?: d
            override fun contains(k: String?) = mem.containsKey(k)
            override fun registerOnSharedPreferenceChangeListener(l: android.content.SharedPreferences.OnSharedPreferenceChangeListener?) {}
            override fun unregisterOnSharedPreferenceChangeListener(l: android.content.SharedPreferences.OnSharedPreferenceChangeListener?) {}
            override fun edit() = object : android.content.SharedPreferences.Editor {
                private val pendentes = mutableMapOf<String, Any?>()
                private val remover = mutableSetOf<String>()
                override fun putString(k: String?, v: String?) = apply { if (k != null) pendentes[k] = v }
                override fun putStringSet(k: String?, v: MutableSet<String>?) = apply { if (k != null) pendentes[k] = v }
                override fun putInt(k: String?, v: Int) = apply { if (k != null) pendentes[k] = v }
                override fun putLong(k: String?, v: Long) = apply { if (k != null) pendentes[k] = v }
                override fun putFloat(k: String?, v: Float) = apply { if (k != null) pendentes[k] = v }
                override fun putBoolean(k: String?, v: Boolean) = apply { if (k != null) pendentes[k] = v }
                override fun remove(k: String?) = apply { if (k != null) remover.add(k) }
                override fun clear() = apply { pendentes.clear(); remover.addAll(mem.keys) }
                override fun commit(): Boolean { apply(); return true }
                override fun apply() { remover.forEach { mem.remove(it) }; mem.putAll(pendentes) }
            }
        }
        return SettingsStore.forTesting(prefs)
    }

    @Test fun guarda_e_le_cookie_pelo_host() {
        val store = criarStore()
        val jar = PersistentCookieJar(store)
        val url = "http://192.168.50.10:8080/login".toHttpUrl()
        val cookie = Cookie.Builder()
            .name("jarvis_sessao").value("abc").domain(url.host)
            .expiresAt(System.currentTimeMillis() + 3600_000).build()
        jar.saveFromResponse(url, listOf(cookie))
        val devolvido = jar.loadForRequest(url)
        assertEquals(1, devolvido.size)
        assertEquals("jarvis_sessao", devolvido[0].name)
        assertEquals("abc", devolvido[0].value)
    }

    @Test fun cookie_expirado_nao_e_devolvido() {
        val store = criarStore()
        val jar = PersistentCookieJar(store)
        val url = "http://jarvis.local/".toHttpUrl()
        val velho = Cookie.Builder().name("x").value("y").domain(url.host)
            .expiresAt(System.currentTimeMillis() - 1000).build()
        jar.saveFromResponse(url, listOf(velho))
        assertEquals(0, jar.loadForRequest(url).size)
    }

    @Test fun limpar_remove_tudo() {
        val store = criarStore()
        val jar = PersistentCookieJar(store)
        val url = "http://x/".toHttpUrl()
        val c = Cookie.Builder().name("s").value("v").domain(url.host)
            .expiresAt(System.currentTimeMillis() + 10_000).build()
        jar.saveFromResponse(url, listOf(c))
        jar.limpar()
        assertEquals(0, jar.loadForRequest(url).size)
    }
}
