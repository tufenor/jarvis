package com.jarvis.companion.data.network

import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonNames

/**
 * Espelhos tolerantes dos retratos vindos do JARVIS. O backend pode acrescentar
 * campos sem quebrar o app: `ignoreUnknownKeys = true`. Só serializamos o que
 * realmente usamos na UI.
 */
val jarvisJson: Json = Json {
    ignoreUnknownKeys = true
    coerceInputValues = true
    explicitNulls = false
}

@Serializable
data class LoginRequest(val senha: String)

@Serializable
data class ComandoRequest(val texto: String)

@Serializable
@OptIn(ExperimentalSerializationApi::class)
data class PresencaRequest(
    val presente: Boolean?,
    val origem: String,
    val evento: String,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @JsonNames("precisao_m") val precisaoM: Float? = null,
)

@Serializable
data class AgenteRetrato(
    val estado: String = "repouso",
    val detalhe: String = "",
    @OptIn(ExperimentalSerializationApi::class) @JsonNames("ultima_fala") val ultimaFala: String = "",
    @OptIn(ExperimentalSerializationApi::class) @JsonNames("ultima_resposta") val ultimaResposta: String = "",
)

@Serializable
data class PlacaRetrato(
    val online: Boolean = false,
    val temperatura: Double? = null,
    val umidade: Double? = null,
    val movimento: Boolean? = null,
)

@Serializable
data class CerebroRetrato(val nome: String = "", val online: Boolean = true)

@Serializable
data class PresencaRetrato(
    val presente: Boolean? = null,
    val origem: String = "",
    val evento: String = "",
    val quando: String = "",
    val bateria: Int? = null,
    val carregando: Boolean? = null,
)

@Serializable
data class SistemaRetrato(val cpu: Double = 0.0, val memoria: Double = 0.0)

@Serializable
data class Retrato(
    val tipo: String = "estado",
    val agente: AgenteRetrato = AgenteRetrato(),
    val placa: PlacaRetrato = PlacaRetrato(),
    val cerebro: CerebroRetrato = CerebroRetrato(),
    val sistema: SistemaRetrato = SistemaRetrato(),
    @OptIn(ExperimentalSerializationApi::class) @JsonNames("presencas_moveis") val presencasMoveis: Map<String, PresencaRetrato> = emptyMap(),
    @OptIn(ExperimentalSerializationApi::class) @JsonNames("presenca_mobile") val presencaMobile: PresencaRetrato = PresencaRetrato(),
)
