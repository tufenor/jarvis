package com.jarvis.companion

import com.jarvis.companion.data.settings.SettingsStore
import org.junit.Assert.assertEquals
import org.junit.Test

class SettingsStoreTest {
    @Test fun normaliza_url_sem_barra_final() {
        assertEquals("https://x", SettingsStore.normalize("https://x/"))
        assertEquals("http://x:8080", SettingsStore.normalize("x:8080"))
        assertEquals("", SettingsStore.normalize("   "))
        assertEquals("https://host", SettingsStore.normalize("https://host///"))
    }
}
