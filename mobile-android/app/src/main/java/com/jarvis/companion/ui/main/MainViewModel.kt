package com.jarvis.companion.ui.main

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.jarvis.companion.core.di.Services
import com.jarvis.companion.data.network.ConexaoCanal
import com.jarvis.companion.data.network.Retrato
import com.jarvis.companion.data.presence.PresenceReporter
import com.jarvis.companion.data.network.PcAgentClient
import com.jarvis.companion.data.network.WakeOnLan
import com.jarvis.companion.data.voz.Hotword
import com.jarvis.companion.data.voz.VozMovel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.launch

class MainViewModel(private val services: Services) : ViewModel() {

    private val _aviso = MutableStateFlow<String?>(null)
    val aviso: StateFlow<String?> = _aviso.asStateFlow()

    val conexao: StateFlow<ConexaoCanal> = services.channel.conexao
    val retrato: StateFlow<Retrato?> = services.channel.ultimo

    /** Estado derivado para a UI, compilado num único objeto. */
    val visao: StateFlow<MainVisao> = combine(
        services.channel.conexao, services.channel.ultimo, services.settings.state,
    ) { canal, retrato, cfg ->
        MainVisao(conexao = canal, retrato = retrato, nomeAparelho = cfg.deviceName,
                  modoEconomico = cfg.batterySaver, operador = cfg.operatorName)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000),
              MainVisao(ConexaoCanal.Offline, null, "a53", false, "SENHOR"))

    // Voz do celular
    val vozEstado: StateFlow<VozMovel.Estado> = services.voz.estado
    val vozParcial: StateFlow<String> = services.voz.parcial
    private val _modoContinuo = MutableStateFlow(false)
    val modoContinuo: StateFlow<Boolean> = _modoContinuo.asStateFlow()

    init {
        services.channel.conectar()

        // Toda vez que a ultimaResposta mudar, se o modo de voz estiver ativo
        // a resposta e falada automaticamente no alto-falante do celular.
        services.channel.ultimo
            .map { it?.agente?.ultimaResposta.orEmpty() }
            .distinctUntilChanged()
            .filterNotNull()
            .onEach { resposta ->
                if (resposta.isBlank()) return@onEach
                services.voz.falar(resposta) {
                    if (_modoContinuo.value) iniciarEscutaHotword()
                }
            }
            .launchIn(viewModelScope)
    }

    override fun onCleared() {
        services.channel.desconectar()
        services.voz.desligar()
    }

    /** Toque unico: ouve uma vez, envia como comando. */
    fun falarUmaVez() = viewModelScope.launch {
        services.voz.ouvir { texto ->
            if (!texto.isNullOrBlank()) enviar(texto)
        }
    }

    /** Toggle do modo continuo com hotword "Jarvis". */
    fun alternarModoContinuo() {
        _modoContinuo.value = !_modoContinuo.value
        if (_modoContinuo.value) iniciarEscutaHotword() else services.voz.pararTudo()
    }

    private fun iniciarEscutaHotword() {
        if (!_modoContinuo.value) return
        services.voz.ouvir { texto ->
            val comando = Hotword.extrairComando(texto)
            when {
                comando == null -> {
                    if (_modoContinuo.value) iniciarEscutaHotword()
                }
                comando.isBlank() -> {
                    services.voz.falar("Estou aqui.") { iniciarEscutaHotword() }
                }
                else -> enviar(comando)
            }
        }
    }

    fun enviar(texto: String) = viewModelScope.launch {
        if (texto.isBlank()) return@launch
        runCatching { services.api.comando(texto) }
            .onSuccess { _aviso.value = "Comando enviado." }
            .onFailure { _aviso.value = "Falhou: ${it.message}" }
    }

    fun ouvirNoPc() = viewModelScope.launch {
        runCatching { services.api.escutar() }
            .onSuccess { _aviso.value = "Microfone do PC aberto." }
            .onFailure { _aviso.value = "Não consegui abrir o microfone." }
    }

    fun cancelar() = viewModelScope.launch {
        runCatching { services.api.cancelar() }
            .onSuccess { _aviso.value = "Tarefa cancelada." }
            .onFailure { _aviso.value = "Não consegui cancelar." }
    }

    fun verificarPresenca() = viewModelScope.launch {
        when (val r = services.presence.reportar("manual")) {
            is PresenceReporter.Resultado.Enviado ->
                _aviso.value = if (r.temGps) "Presença enviada com GPS."
                               else "Enviado sem GPS (sem permissão ou sem sinal)."
            is PresenceReporter.Resultado.Erro -> _aviso.value = "Falhou: ${r.mensagem}"
        }
    }

    fun limparAviso() { _aviso.value = null }
    fun setAviso(t: String) { _aviso.value = t }

    // ---- acoes no PC via pc_agent / WoL -------------------------------

    suspend fun iniciarJarvisPC(): Boolean {
        val r = services.pcAgent.iniciarJarvis()
        return r == PcAgentClient.Resultado.JaRodando || r == PcAgentClient.Resultado.Iniciando
    }

    suspend fun pararJarvisPC() {
        _aviso.value = when (services.pcAgent.pararJarvis()) {
            PcAgentClient.Resultado.Parado -> "JARVIS parado."
            PcAgentClient.Resultado.SemToken -> "Token do agente nao configurado."
            PcAgentClient.Resultado.SemAgente -> "pc_agent nao responde."
            else -> "Falhou ao parar."
        }
    }

    suspend fun acordarPc() {
        _aviso.value = if (WakeOnLan.acordar()) "Pacote WoL enviado." else "Falhou ao enviar WoL."
    }

    suspend fun suspenderPc() {
        _aviso.value = when (services.pcAgent.suspenderPc()) {
            PcAgentClient.Resultado.Suspendendo -> "PC suspendendo…"
            PcAgentClient.Resultado.SemToken -> "Token do agente nao configurado."
            PcAgentClient.Resultado.SemAgente -> "pc_agent nao responde."
            else -> "Falhou ao suspender."
        }
    }

    suspend fun desligarPc() {
        _aviso.value = when (services.pcAgent.desligarPc()) {
            PcAgentClient.Resultado.Desligando -> "Desligamento agendado (30 s)."
            PcAgentClient.Resultado.SemToken -> "Token do agente nao configurado."
            PcAgentClient.Resultado.SemAgente -> "pc_agent nao responde."
            else -> "Falhou ao desligar."
        }
    }
}

data class MainVisao(
    val conexao: ConexaoCanal,
    val retrato: Retrato?,
    val nomeAparelho: String,
    val modoEconomico: Boolean,
    val operador: String = "SENHOR",
)
