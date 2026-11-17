package com.jarvis.companion

import com.jarvis.companion.data.voz.Hotword
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class HotwordTest {
    @Test fun reconhece_jarvis_e_variantes() {
        assertEquals("abra o navegador",
            Hotword.extrairComando("Jarvis, abra o navegador"))
        assertEquals("que horas sao",
            Hotword.extrairComando("Javis que horas sao"))
        assertEquals("", Hotword.extrairComando("Jarvis"))
    }

    @Test fun ignora_quando_hotword_nao_aparece() {
        assertNull(Hotword.extrairComando("abra o navegador"))
        assertNull(Hotword.extrairComando(""))
        assertNull(Hotword.extrairComando(null))
    }

    @Test fun ignora_hotword_no_meio_da_frase() {
        // Evita falso positivo com TV ("…ontem o Jarvis…").
        assertNull(Hotword.extrairComando("a reportagem de ontem jarvis teve audiencia"))
    }

    @Test fun aceita_hotword_na_primeira_ou_segunda_palavra() {
        assertEquals("tudo bem",
            Hotword.extrairComando("oi Jarvis tudo bem"))
    }
}
