package com.jarvis.companion.data.voz

/**
 * Detecta "Jarvis" no texto reconhecido pelo microfone do celular e devolve
 * o resto da frase como comando. Fica aqui (puro, sem Android) para ser
 * testado como qualquer Kotlin.
 */
object Hotword {
    // Mantemos APENAS variantes muito proximas de "jarvis" em pt-BR; palavras
    // curtas (jarvi, jarvs, javir) geravam falso positivo com TV ligada.
    private val VARIANTES = setOf("jarvis", "javis")

    // Hotword tem que estar nas DUAS primeiras palavras da frase, nao no meio.
    private const val POSICAO_MAX = 1

    /**
     * @return comando depois do hotword (string vazia se so disse "Jarvis"),
     *         ou null se o hotword nao apareceu na posicao esperada.
     */
    fun extrairComando(texto: String?): String? {
        if (texto.isNullOrBlank()) return null
        val norm = texto.trim().lowercase()
            .replace(Regex("[,.;:!?]"), " ")
            .replace(Regex("\\s+"), " ")
        val palavras = norm.split(' ')
        val idx = palavras.indexOfFirst { it in VARIANTES }
        if (idx < 0 || idx > POSICAO_MAX) return null
        return palavras.drop(idx + 1).joinToString(" ").trim()
    }
}
