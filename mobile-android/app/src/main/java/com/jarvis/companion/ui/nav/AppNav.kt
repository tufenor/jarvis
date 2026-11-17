package com.jarvis.companion.ui.nav

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.jarvis.companion.core.di.Services
import com.jarvis.companion.data.auth.AuthEstado
import com.jarvis.companion.data.network.PcAgentClient
import com.jarvis.companion.data.network.WakeOnLan
import com.jarvis.companion.ui.auth.LoginScreen
import com.jarvis.companion.ui.diagnostics.DiagnosticsScreen
import com.jarvis.companion.ui.ditado.DitadoScreen
import com.jarvis.companion.ui.main.MainScreen
import com.jarvis.companion.ui.settings.SettingsScreen
import kotlinx.coroutines.launch

object Rotas {
    const val LOGIN = "login"
    const val MAIN = "main"
    const val SETTINGS = "settings"
    const val DIAG = "diag"
    const val DITADO = "ditado"
}

private enum class Fase { Procurando, NaoAchou, Pronto }

@Composable
fun AppNav(services: Services) {
    val nav = rememberNavController()
    val auth by services.auth.estado.collectAsState()
    val baseUrl = services.settings.state.collectAsState().value.baseUrl
    val urlConfigurada = baseUrl.isNotBlank()

    var fase by remember { mutableStateOf(if (urlConfigurada) Fase.Pronto else Fase.Procurando) }
    var tentativa by remember { mutableStateOf(0) }

    LaunchedEffect(tentativa, urlConfigurada) {
        if (urlConfigurada) {
            fase = Fase.Pronto
            return@LaunchedEffect
        }
        fase = Fase.Procurando
        val achado = services.discovery.descobrir()
        if (achado != null) {
            services.settings.updateBaseUrl(achado)
            fase = Fase.Pronto
        } else {
            fase = Fase.NaoAchou
        }
    }

    when (fase) {
        Fase.Procurando -> TelaProcurando()
        Fase.NaoAchou -> TelaAcordarPc(
            services = services,
            aoReiniciar = { tentativa++ },
        )
        Fase.Pronto -> {
            val inicial = when {
                !urlConfigurada -> Rotas.SETTINGS
                auth == AuthEstado.Deslogado -> Rotas.LOGIN
                else -> Rotas.MAIN
            }
            NavHost(navController = nav, startDestination = inicial) {
                composable(Rotas.LOGIN) {
                    LoginScreen(
                        services = services,
                        aoEntrar = { nav.navigate(Rotas.MAIN) { popUpTo(Rotas.LOGIN) { inclusive = true } } },
                        abrirServidor = { nav.navigate(Rotas.SETTINGS) },
                    )
                }
                composable(Rotas.MAIN) {
                    MainScreen(
                        services = services,
                        abrirSettings = { nav.navigate(Rotas.SETTINGS) },
                        abrirDiagnostico = { nav.navigate(Rotas.DIAG) },
                        abrirDitado = { nav.navigate(Rotas.DITADO) },
                        sair = { services.auth.sair(); nav.navigate(Rotas.LOGIN) { popUpTo(Rotas.MAIN) { inclusive = true } } },
                    )
                }
                composable(Rotas.SETTINGS) {
                    SettingsScreen(services = services, voltar = { nav.popBackStack() })
                }
                composable(Rotas.DIAG) {
                    DiagnosticsScreen(services = services, voltar = { nav.popBackStack() })
                }
                composable(Rotas.DITADO) {
                    DitadoScreen(services = services, voltar = { nav.popBackStack() })
                }
            }
        }
    }
}

@Composable
private fun TelaProcurando() {
    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(
            modifier = Modifier.fillMaxSize().padding(24.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            CircularProgressIndicator()
            Text(
                text = "Procurando o JARVIS na rede...",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onBackground,
                modifier = Modifier.padding(top = 24.dp),
            )
        }
    }
}

@Composable
private fun TelaAcordarPc(
    services: com.jarvis.companion.core.di.Services,
    aoReiniciar: () -> Unit,
) {
    val escopo = rememberCoroutineScope()
    var status by remember { mutableStateOf<String?>(null) }
    var trabalhando by remember { mutableStateOf(false) }

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(
            modifier = Modifier.fillMaxSize().padding(24.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = "JARVIS não respondeu.",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onBackground,
            )
            Spacer(Modifier.height(16.dp))
            Text(
                text = "Posso acordar o PC e iniciar o JARVIS. Toque uma vez.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onBackground,
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(24.dp))
            Button(enabled = !trabalhando, onClick = {
                escopo.launch {
                    trabalhando = true
                    try {
                        // 1) Se está na mesma rede, o pacote local resolve rápido.
                        status = "Pacote mágico na rede local…"
                        WakeOnLan.acordar()

                        // 2) Em paralelo, pede ao relé HTTPS configurado pra ESP32
                        // fazer o mesmo. Funciona quando o celular está fora de casa.
                        status = "Pedindo pro relé em casa acordar o PC…"
                        services.rele.acordarRemoto()

                        // 3) Tenta pc_agent agora (PC acordado ou nunca desligou).
                        status = "Pedindo pro PC iniciar o JARVIS…"
                        var r = services.pcAgent.iniciarJarvis()

                        // 4) Se o pc_agent não responde, espera o PC subir e tenta de novo.
                        var tentativasExtras = 0
                        while (r == PcAgentClient.Resultado.SemAgente && tentativasExtras < 12) {
                            kotlinx.coroutines.delay(5_000)
                            r = services.pcAgent.iniciarJarvis()
                            tentativasExtras++
                        }

                        when (r) {
                            PcAgentClient.Resultado.JaRodando,
                            PcAgentClient.Resultado.Iniciando -> {
                                status = "JARVIS subindo… conectando…"
                                kotlinx.coroutines.delay(4_000)
                                aoReiniciar()
                            }
                            PcAgentClient.Resultado.SemAgente -> {
                                // Última checagem: o relé consegue ver o heartbeat?
                                if (services.rele.pcEstaOnline()) {
                                    status = "PC vivo (visto pelo relé). Tentando reconectar…"
                                    aoReiniciar()
                                } else {
                                    status = "PC não acordou. Veja BIOS/UEFI/WoL ou se a ESP32 está on."
                                }
                            }
                            PcAgentClient.Resultado.SemToken ->
                                status = "Token do agente não configurado no app."
                            else -> status = "O agente recusou o comando."
                        }
                    } finally {
                        trabalhando = false
                    }
                }
            }) { Text("ABRIR JARVIS") }
            Spacer(Modifier.height(12.dp))
            OutlinedButton(enabled = !trabalhando, onClick = aoReiniciar) { Text("TENTAR DE NOVO") }
            status?.let {
                Spacer(Modifier.height(16.dp))
                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onBackground)
            }
        }
    }
}
