package com.jarvis.companion

import com.jarvis.companion.data.network.WakeOnLan
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test

class WakeOnLanTest {

    @Test fun pacote_tem_6_bytes_ff_mais_16_vezes_o_mac() {
        val pacote = WakeOnLan.montarPacote("01:02:03:04:05:06")
        assertEquals(6 + 16 * 6, pacote.size)
        val cabec = ByteArray(6) { 0xFF.toByte() }
        assertArrayEquals(cabec, pacote.sliceArray(0 until 6))
        val mac = byteArrayOf(0x01, 0x02, 0x03, 0x04, 0x05, 0x06)
        for (i in 0 until 16) {
            assertArrayEquals(mac, pacote.sliceArray((6 + i * 6) until (6 + (i + 1) * 6)))
        }
    }

    @Test fun aceita_mac_com_tracos() {
        val a = WakeOnLan.montarPacote("48:A4:72:35:4F:E9")
        val b = WakeOnLan.montarPacote("48-A4-72-35-4F-E9")
        assertArrayEquals(a, b)
    }

    @Test(expected = IllegalArgumentException::class) fun mac_invalido_dispara() {
        WakeOnLan.montarPacote("48:A4:72")
    }
}
