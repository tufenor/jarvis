package com.jarvis.companion.data.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress

/**
 * Wake-on-LAN: monta o pacote mágico (6 bytes 0xFF + 16 cópias do MAC) e manda
 * por UDP broadcast nas portas 7 e 9. Funciona quando o celular e o PC estão
 * na MESMA rede Wi-Fi/Ethernet — pelo Tailscale (L3) o pacote L2 não chega.
 *
 * O PC precisa ter Wake-on-LAN ligado na BIOS/UEFI, "Magic Packet" ligado no
 * driver do adaptador e hibernação desligada (`powercfg -h off`).
 */
object WakeOnLan {

    /** MAC do adaptador Wi-Fi do PC deste usuário. */
    const val MAC_PC = "48:A4:72:35:4F:E9"

    /**
     * Envia o pacote mágico. @param mac no formato `AA:BB:CC:DD:EE:FF` (`-` também aceito).
     * @return true se pelo menos um broadcast foi enviado sem exceção.
     */
    suspend fun acordar(
        mac: String = MAC_PC,
        broadcast: String = "255.255.255.255",
    ): Boolean = withContext(Dispatchers.IO) {
        val payload = montarPacote(mac)
        val endereco = InetAddress.getByName(broadcast)
        var algumSucesso = false
        for (porta in intArrayOf(9, 7)) {
            runCatching {
                DatagramSocket().use { socket ->
                    socket.broadcast = true
                    socket.send(DatagramPacket(payload, payload.size, endereco, porta))
                }
                algumSucesso = true
            }
        }
        algumSucesso
    }

    internal fun montarPacote(mac: String): ByteArray {
        val bytes = mac.split(':', '-').map { it.toInt(16).toByte() }.toByteArray()
        require(bytes.size == 6) { "MAC inválido: $mac" }
        val buf = ByteArray(6 + 16 * 6)
        for (i in 0 until 6) buf[i] = 0xFF.toByte()
        for (i in 0 until 16) System.arraycopy(bytes, 0, buf, 6 + i * 6, 6)
        return buf
    }
}
