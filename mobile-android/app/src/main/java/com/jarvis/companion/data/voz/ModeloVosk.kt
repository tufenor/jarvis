package com.jarvis.companion.data.voz

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.zip.ZipInputStream

/**
 * Baixa, descompacta e serve o caminho local do modelo Vosk pt-BR.
 *
 * Nada e feito sem chamada explicita a [baixarSePreciso]. O tamanho (~31 MB) e
 * mostrado na tela antes do download. Uma vez baixado, o modelo fica em
 * `getFilesDir()/vosk-model-small-pt-0.3/` e nao e baixado de novo. O usuario
 * pode [apagar] a qualquer momento.
 */
class ModeloVosk(private val ctx: Context) {

    companion object {
        const val NOME_MODELO = "vosk-model-small-pt-0.3"
        // URL oficial do catalogo da Alphacephei. Zip de ~31 MB.
        const val URL_ZIP = "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip"
        const val TAMANHO_ESTIMADO_MB = 31
    }

    val pasta: File = File(ctx.filesDir, NOME_MODELO)

    fun jaBaixado(): Boolean = pasta.exists() && pasta.isDirectory && (pasta.listFiles()?.isNotEmpty() == true)

    fun apagar(): Boolean = pasta.deleteRecursively()

    /**
     * Baixa + descompacta. Emite progresso (0..100) ou -1 para "concluido com sucesso".
     * Erros viram IOException dentro do flow.
     */
    fun baixarSePreciso(): Flow<Int> = flow {
        if (jaBaixado()) { emit(-1); return@flow }
        val tmp = File(ctx.cacheDir, "$NOME_MODELO.zip")
        tmp.parentFile?.mkdirs()
        val conn = (URL(URL_ZIP).openConnection() as HttpURLConnection).apply {
            connectTimeout = 15_000
            readTimeout = 60_000
            requestMethod = "GET"
        }
        try {
            val total = conn.contentLengthLong.takeIf { it > 0 } ?: (TAMANHO_ESTIMADO_MB * 1024L * 1024L)
            conn.inputStream.use { input ->
                tmp.outputStream().use { out ->
                    val buf = ByteArray(16 * 1024)
                    var baixado = 0L
                    var lido: Int
                    while (input.read(buf).also { lido = it } > 0) {
                        out.write(buf, 0, lido)
                        baixado += lido
                        val pct = ((baixado * 100L) / total).toInt().coerceIn(0, 99)
                        emit(pct)
                    }
                }
            }
        } finally {
            conn.disconnect()
        }
        // descompacta
        pasta.mkdirs()
        ZipInputStream(tmp.inputStream()).use { zip ->
            var entry = zip.nextEntry
            while (entry != null) {
                val nomeRelativo = entry.name.substringAfter(NOME_MODELO + "/", entry.name)
                val destino = File(pasta, nomeRelativo)
                if (entry.isDirectory) {
                    destino.mkdirs()
                } else {
                    destino.parentFile?.mkdirs()
                    destino.outputStream().use { out -> zip.copyTo(out) }
                }
                entry = zip.nextEntry
            }
        }
        tmp.delete()
        emit(-1)
    }.flowOn(Dispatchers.IO)
}
