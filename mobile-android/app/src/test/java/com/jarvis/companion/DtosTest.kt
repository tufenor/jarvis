package com.jarvis.companion

import com.jarvis.companion.data.network.Retrato
import com.jarvis.companion.data.network.jarvisJson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Qualquer campo novo no backend não pode quebrar o app: desserialização
 * tolerante e com defaults.
 */
class DtosTest {
    @Test fun ignora_campos_desconhecidos_e_usa_defaults() {
        val json = """
        {
          "tipo": "estado",
          "agente": {"estado": "ouvindo", "detalhe": "aqui", "futuro": 1},
          "placa": {"online": true, "temperatura": 23.4, "umidade": 55.2},
          "campo_que_nao_existe_ainda": [1,2,3]
        }
        """.trimIndent()
        val r = jarvisJson.decodeFromString(Retrato.serializer(), json)
        assertEquals("ouvindo", r.agente.estado)
        assertEquals("aqui", r.agente.detalhe)
        assertEquals(true, r.placa.online)
        assertEquals(23.4, r.placa.temperatura!!, 0.01)
        assertEquals("", r.cerebro.nome)                  // default
        assertTrue(r.presencasMoveis.isEmpty())
    }

    @Test fun presencas_moveis_sao_mapeadas() {
        val json = """
        {
          "presencas_moveis": {
            "a53": {"presente": true, "origem": "a53", "evento": "sat", "quando": "2026-11-06T17:00:00", "bateria": 73}
          }
        }
        """.trimIndent()
        val r = jarvisJson.decodeFromString(Retrato.serializer(), json)
        val p = r.presencasMoveis["a53"]!!
        assertEquals(true, p.presente)
        assertEquals(73, p.bateria)
    }
}
