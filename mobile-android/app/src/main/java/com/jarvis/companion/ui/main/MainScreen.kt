package com.jarvis.companion.ui.main

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Logout
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material.icons.outlined.Bedtime
import androidx.compose.material.icons.outlined.PowerSettingsNew
import androidx.compose.material.icons.outlined.PlayArrow
import androidx.compose.material.icons.outlined.Send
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Stop
import androidx.compose.material.icons.outlined.Troubleshoot
import androidx.compose.material.icons.outlined.Wifi
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.jarvis.companion.R
import com.jarvis.companion.core.di.Services
import com.jarvis.companion.data.network.ConexaoCanal
import com.jarvis.companion.data.voz.VozMovel
import com.jarvis.companion.ui.common.*
import com.jarvis.companion.ui.theme.*
import kotlinx.coroutines.launch
import java.util.Calendar

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(
    services: Services,
    abrirSettings: () -> Unit,
    abrirDiagnostico: () -> Unit,
    abrirDitado: () -> Unit = {},
    sair: () -> Unit,
) {
    val vm: MainViewModel = viewModel(factory = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T = MainViewModel(services) as T
    })

    val visao by vm.visao.collectAsState()
    val aviso by vm.aviso.collectAsState()
    val vozEstado by vm.vozEstado.collectAsState()
    val vozParcial by vm.vozParcial.collectAsState()
    val modoContinuo by vm.modoContinuo.collectAsState()
    val escopo = rememberCoroutineScope()

    val micPerm = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) vm.falarUmaVez()
    }

    var comando by remember { mutableStateOf("") }
    var pedindoConfirmacao by remember { mutableStateOf<ConfirmarAcao?>(null) }

    val estadoNucleo = estadoNucleoPara(visao.conexao, vozEstado,
            agente = visao.retrato?.agente?.estado)
    val horaDeAgora = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)

    Box(Modifier.fillMaxSize()) {
        BackgroundHud()

        Scaffold(
            containerColor = androidx.compose.ui.graphics.Color.Transparent,
            topBar = {
                HudTopBar(
                    conexao = visao.conexao,
                    nomeAparelho = visao.nomeAparelho,
                    aoDiagnostico = abrirDiagnostico,
                    aoDitado = abrirDitado,
                    aoSettings = abrirSettings,
                    aoSair = sair,
                )
            },
            snackbarHost = {
                AnimatedVisibility(aviso != null, enter = fadeIn(), exit = fadeOut()) {
                    aviso?.let {
                        Snackbar(
                            modifier = Modifier.padding(12.dp),
                            containerColor = SuperficieAlta,
                            contentColor = Texto,
                            action = { TextButton(onClick = vm::limparAviso) { Text("OK", color = NucleoAzul) } },
                        ) { Text(it) }
                    }
                }
            },
        ) { padding ->
            Column(
                modifier = Modifier
                    .padding(padding)
                    .padding(horizontal = 16.dp)
                    .verticalScroll(rememberScrollState())
                    .semantics { contentDescription = "Painel do JARVIS" },
                verticalArrangement = Arrangement.spacedBy(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Spacer(Modifier.height(4.dp))
                HeroHeader(
                    operador = visao.operador,
                    horaHoje = horaDeAgora,
                    estado = estadoNucleo,
                    rotulo = rotuloVoz(vozEstado, modoContinuo),
                )
                MicPainel(
                    estado = vozEstado,
                    parcial = vozParcial,
                    modoContinuo = modoContinuo,
                    aoTocar = { micPerm.launch(Manifest.permission.RECORD_AUDIO) },
                    aoAlternar = { vm.alternarModoContinuo() },
                )
                SistemaBarra(visao)
                GradeAcoes(
                    ativo = visao.conexao is ConexaoCanal.Online,
                    onIniciarJarvis = {
                        escopo.launch {
                            when (vm.iniciarJarvisPC()) {
                                true -> vm.setAviso("JARVIS pedido ao PC.")
                                false -> vm.setAviso("PC não respondeu.")
                            }
                        }
                    },
                    onPararJarvis = { pedindoConfirmacao = ConfirmarAcao.PararJarvis },
                    onLigarPc = { escopo.launch { vm.acordarPc() } },
                    onSuspenderPc = { pedindoConfirmacao = ConfirmarAcao.SuspenderPc },
                    onDesligarPc = { pedindoConfirmacao = ConfirmarAcao.DesligarPc },
                )
                BlocoComando(
                    texto = comando,
                    onTexto = { comando = it },
                    enviar = { if (comando.isNotBlank()) { vm.enviar(comando); comando = "" } },
                    cancelar = vm::cancelar,
                )
                BlocoResposta(visao)
                Spacer(Modifier.height(16.dp))
            }
        }
    }

    pedindoConfirmacao?.let { acao ->
        AlertDialog(
            onDismissRequest = { pedindoConfirmacao = null },
            containerColor = SuperficieAlta,
            titleContentColor = Texto,
            textContentColor = TextoSuave,
            title = { Text(acao.titulo) },
            text = { Text(acao.detalhe) },
            confirmButton = {
                TextButton(onClick = {
                    pedindoConfirmacao = null
                    escopo.launch {
                        when (acao) {
                            ConfirmarAcao.PararJarvis -> vm.pararJarvisPC()
                            ConfirmarAcao.SuspenderPc -> vm.suspenderPc()
                            ConfirmarAcao.DesligarPc -> vm.desligarPc()
                        }
                    }
                }) { Text("CONFIRMAR", color = PerigoVermelho) }
            },
            dismissButton = {
                TextButton(onClick = { pedindoConfirmacao = null }) {
                    Text("CANCELAR", color = TextoSuave)
                }
            },
        )
    }
}

private enum class ConfirmarAcao(val titulo: String, val detalhe: String) {
    PararJarvis("Parar o JARVIS?", "Encerra o processo no PC. O painel web e esta conversa caem até você reiniciar."),
    SuspenderPc("Suspender o PC?", "Coloca o PC em espera (S3). Wake-on-LAN só acorda se estiver pronto."),
    DesligarPc("Desligar o PC?", "Agendado para 30 segundos. Você pode cancelar nesse tempo pelo painel do PC."),
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HudTopBar(
    conexao: ConexaoCanal,
    nomeAparelho: String,
    aoDiagnostico: () -> Unit,
    aoDitado: () -> Unit = {},
    aoSettings: () -> Unit,
    aoSair: () -> Unit,
) {
    CenterAlignedTopAppBar(
        title = {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    "J · A · R · V · I · S",
                    style = MaterialTheme.typography.titleLarge.copy(
                        fontFamily = FontFamily.Monospace,
                        letterSpacing = 4.sp,
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 15.sp,
                    ),
                    color = Texto,
                )
                Text(
                    "NODE · ${nomeAparelho.uppercase()}",
                    style = MaterialTheme.typography.labelMedium.copy(
                        fontFamily = FontFamily.Monospace, letterSpacing = 1.5.sp, fontSize = 9.sp,
                    ),
                    color = TextoAtenuado,
                )
            }
        },
        navigationIcon = {
            IconButton(onClick = aoDiagnostico) {
                androidx.compose.material3.Icon(
                    Icons.Outlined.Troubleshoot,
                    contentDescription = "Diagnóstico", tint = TextoSuave,
                )
            }
        },
        actions = {
            ConexaoChip(conexao)
            Spacer(Modifier.width(2.dp))
            IconButton(onClick = aoDitado) {
                androidx.compose.material3.Icon(
                    androidx.compose.material.icons.Icons.Outlined.Mic,
                    contentDescription = "Ditado offline", tint = TextoSuave,
                )
            }
            IconButton(onClick = aoSettings) {
                androidx.compose.material3.Icon(
                    Icons.Outlined.Settings,
                    contentDescription = "Configurações", tint = TextoSuave,
                )
            }
            IconButton(onClick = aoSair) {
                androidx.compose.material3.Icon(
                    Icons.Filled.Logout,
                    contentDescription = "Sair da sessão", tint = TextoAtenuado,
                )
            }
        },
        colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
            containerColor = androidx.compose.ui.graphics.Color.Transparent,
            scrolledContainerColor = androidx.compose.ui.graphics.Color.Transparent,
        ),
    )
}

@Composable
private fun HeroHeader(operador: String, horaHoje: Int, estado: EstadoNucleo, rotulo: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Box(contentAlignment = Alignment.Center) {
            HeroNucleo(estado = estado)
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    rotulo,
                    style = MaterialTheme.typography.labelLarge.copy(
                        fontFamily = FontFamily.Monospace, letterSpacing = 2.sp, fontSize = 10.sp,
                    ),
                    color = estado.cores().first,
                )
            }
        }
        Spacer(Modifier.height(6.dp))
        Text(
            saudacao(operador, horaHoje),
            style = MaterialTheme.typography.titleLarge.copy(
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Medium,
                letterSpacing = 1.sp,
                fontSize = 15.sp,
            ),
            color = Texto,
        )
        Text(
            "AO SEU DISPOR.",
            style = MaterialTheme.typography.labelMedium.copy(
                fontFamily = FontFamily.Monospace, letterSpacing = 1.8.sp, fontSize = 10.sp,
            ),
            color = TextoSuave,
        )
    }
}

@Composable
private fun MicPainel(
    estado: VozMovel.Estado,
    parcial: String,
    modoContinuo: Boolean,
    aoTocar: () -> Unit,
    aoAlternar: () -> Unit,
) {
    GlassCard(corBorda = (if (modoContinuo) NucleoMagenta else NucleoAzul).copy(alpha = 0.5f)) {
        Row(verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            MicHero(
                ativo = estado == VozMovel.Estado.Ouvindo ||
                        estado == VozMovel.Estado.Processando ||
                        estado == VozMovel.Estado.Falando,
                modoContinuo = modoContinuo, aoTocar = aoTocar,
            )
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                val cor = if (modoContinuo) NucleoMagenta else NucleoAzul
                Text(
                    if (modoContinuo) "ESCUTA CONTÍNUA" else "TOQUE PARA FALAR",
                    style = MaterialTheme.typography.labelLarge.copy(
                        fontFamily = FontFamily.Monospace, letterSpacing = 2.sp,
                    ),
                    color = cor,
                )
                if (parcial.isNotBlank()) {
                    Text(
                        "\"$parcial\"",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Texto, maxLines = 3,
                    )
                } else {
                    Text(
                        if (modoContinuo) "Aguardando a palavra \"Jarvis\"…"
                        else "Toque o núcleo para falar uma vez.",
                        style = MaterialTheme.typography.bodySmall, color = TextoSuave,
                    )
                }
                NeonLine(cor = cor.copy(alpha = 0.4f))
                TextButton(onClick = aoAlternar, contentPadding = PaddingValues(0.dp)) {
                    Text(
                        if (modoContinuo) "DESATIVAR" else "ATIVAR CONTÍNUO",
                        style = MaterialTheme.typography.labelLarge.copy(
                            fontFamily = FontFamily.Monospace, letterSpacing = 1.5.sp,
                        ),
                        color = cor,
                    )
                }
            }
        }
    }
}

@Composable
private fun SistemaBarra(v: MainVisao) {
    val placa = v.retrato?.placa
    val agente = v.retrato?.agente
    Row(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        MicroMetrica(
            "PC",
            agente?.estado?.uppercase() ?: "—",
            cor = if (agente != null) NucleoAzul else TextoAtenuado,
            modifier = Modifier.weight(1f),
        )
        MicroMetrica(
            "PLACA",
            if (placa?.online == true) "ON" else "OFF",
            cor = if (placa?.online == true) SucessoVerde else PerigoVermelho,
            modifier = Modifier.weight(1f),
        )
        MicroMetrica(
            "TEMP",
            placa?.temperatura?.let { "${it.toInt()}°" } ?: "—",
            cor = NucleoAmbar,
            modifier = Modifier.weight(1f),
        )
        MicroMetrica(
            "UMID",
            placa?.umidade?.let { "${it.toInt()}%" } ?: "—",
            cor = NucleoMagenta,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun GradeAcoes(
    ativo: Boolean,
    onIniciarJarvis: () -> Unit,
    onPararJarvis: () -> Unit,
    onLigarPc: () -> Unit,
    onSuspenderPc: () -> Unit,
    onDesligarPc: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            "AÇÕES RÁPIDAS",
            style = MaterialTheme.typography.labelLarge.copy(
                fontFamily = FontFamily.Monospace, letterSpacing = 2.sp,
            ),
            color = TextoSuave,
            modifier = Modifier.padding(start = 2.dp, bottom = 2.dp),
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Box(Modifier.weight(1f)) {
                ActionTile(Icons.Outlined.PlayArrow, "INICIAR", NucleoAzul,
                    habilitado = true, aoTocar = onIniciarJarvis)
            }
            Box(Modifier.weight(1f)) {
                ActionTile(Icons.Outlined.Stop, "PARAR", NucleoAmbar,
                    habilitado = ativo, aoTocar = onPararJarvis)
            }
            Box(Modifier.weight(1f)) {
                ActionTile(Icons.Outlined.Wifi, "LIGAR PC", SucessoVerde,
                    habilitado = true, aoTocar = onLigarPc)
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Box(Modifier.weight(1f)) {
                ActionTile(Icons.Outlined.Bedtime, "SUSPENDER", NucleoMagenta,
                    habilitado = true, aoTocar = onSuspenderPc)
            }
            Box(Modifier.weight(2.08f)) {
                ActionTile(Icons.Outlined.PowerSettingsNew, "DESLIGAR", PerigoVermelho,
                    habilitado = true, perigoso = true, aoTocar = onDesligarPc)
            }
        }
    }
}

@Composable
private fun BlocoComando(
    texto: String, onTexto: (String) -> Unit, enviar: () -> Unit, cancelar: () -> Unit,
) {
    GlassCard(corBorda = Contorno) {
        Text(
            "COMANDO MANUAL",
            style = MaterialTheme.typography.labelLarge.copy(
                fontFamily = FontFamily.Monospace, letterSpacing = 2.sp,
            ),
            color = TextoSuave,
        )
        Spacer(Modifier.height(10.dp))
        OutlinedTextField(
            value = texto, onValueChange = onTexto,
            placeholder = {
                Text("Diga o que fazer…",
                    color = TextoAtenuado,
                    style = MaterialTheme.typography.bodyMedium)
            },
            modifier = Modifier.fillMaxWidth(),
            minLines = 1, maxLines = 3,
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = NucleoAzul.copy(alpha = 0.7f),
                unfocusedBorderColor = Contorno,
                focusedContainerColor = Superficie.copy(alpha = 0.4f),
                unfocusedContainerColor = Superficie.copy(alpha = 0.4f),
                cursorColor = NucleoAzul,
            ),
        )
        Spacer(Modifier.height(10.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically) {
            Button(
                onClick = enviar, modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(
                    containerColor = NucleoAzul, contentColor = Fundo,
                ),
            ) {
                androidx.compose.material3.Icon(Icons.Outlined.Send, contentDescription = null,
                    modifier = Modifier.size(16.dp))
                Spacer(Modifier.width(8.dp))
                Text("ENVIAR",
                    style = MaterialTheme.typography.labelLarge.copy(
                        fontFamily = FontFamily.Monospace, letterSpacing = 2.sp,
                    ))
            }
            TextButton(onClick = cancelar) {
                Text("CANCELAR TAREFA",
                    style = MaterialTheme.typography.labelLarge.copy(
                        fontFamily = FontFamily.Monospace, letterSpacing = 1.5.sp,
                    ),
                    color = TextoSuave)
            }
        }
    }
}

@Composable
private fun BlocoResposta(v: MainVisao) {
    val resposta = v.retrato?.agente?.ultimaResposta?.ifBlank { null } ?: "—"
    val fala = v.retrato?.agente?.ultimaFala?.ifBlank { null } ?: "—"
    GlassCard(corBorda = NucleoAzul.copy(alpha = 0.35f)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "RESPOSTA",
                style = MaterialTheme.typography.labelLarge.copy(
                    fontFamily = FontFamily.Monospace, letterSpacing = 2.sp,
                ),
                color = NucleoAzul,
            )
            Spacer(Modifier.weight(1f))
            CoreMark(ativo = resposta != "—")
        }
        Spacer(Modifier.height(10.dp))
        Text(resposta, style = MaterialTheme.typography.bodyLarge, color = Texto)
        Spacer(Modifier.height(8.dp))
        NeonLine()
        Spacer(Modifier.height(6.dp))
        Text(
            "ÚLTIMA FALA · $fala",
            style = MaterialTheme.typography.labelMedium.copy(
                fontFamily = FontFamily.Monospace, letterSpacing = 1.sp,
            ),
            color = TextoAtenuado,
        )
    }
}

@Composable
private fun ConexaoChip(canal: ConexaoCanal) {
    val (texto, cor) = when (canal) {
        ConexaoCanal.Online -> stringResource(R.string.status_online) to SucessoVerde
        ConexaoCanal.Conectando, ConexaoCanal.Reconectando ->
            stringResource(R.string.status_reconnecting) to NucleoAmbar
        ConexaoCanal.AguardandoAuth ->
            stringResource(R.string.status_waiting_auth) to NucleoAmbar
        ConexaoCanal.AguardandoConfig -> "SEM SERVIDOR" to TextoSuave
        ConexaoCanal.Offline -> stringResource(R.string.status_offline) to TextoAtenuado
        is ConexaoCanal.Erro -> stringResource(R.string.status_error) to PerigoVermelho
    }
    StatusChip(texto, cor)
}

@Composable
private fun stringResource(id: Int): String =
    androidx.compose.ui.res.stringResource(id)

private fun rotuloVoz(estado: VozMovel.Estado, modo: Boolean): String = when (estado) {
    VozMovel.Estado.Ouvindo -> "ESCUTANDO"
    VozMovel.Estado.Processando -> "PROCESSANDO"
    VozMovel.Estado.Falando -> "RESPONDENDO"
    VozMovel.Estado.SemSuporte -> "SEM VOZ"
    VozMovel.Estado.SemPermissao -> "SEM PERMISSÃO"
    VozMovel.Estado.Repouso -> if (modo) "AGUARDANDO" else "EM ESPERA"
}

private fun estadoNucleoPara(
    conexao: ConexaoCanal,
    voz: VozMovel.Estado,
    agente: String?,
): EstadoNucleo {
    if (conexao is ConexaoCanal.Erro) return EstadoNucleo.Alerta
    if (conexao is ConexaoCanal.Offline || conexao is ConexaoCanal.AguardandoConfig) return EstadoNucleo.Offline
    return when (voz) {
        VozMovel.Estado.Ouvindo -> EstadoNucleo.Escutando
        VozMovel.Estado.Processando -> EstadoNucleo.Pensando
        VozMovel.Estado.Falando -> EstadoNucleo.Respondendo
        VozMovel.Estado.SemPermissao, VozMovel.Estado.SemSuporte -> EstadoNucleo.Alerta
        VozMovel.Estado.Repouso -> when (agente?.lowercase()) {
            "pensando", "processando" -> EstadoNucleo.Pensando
            "falando", "respondendo" -> EstadoNucleo.Respondendo
            "escutando", "ouvindo" -> EstadoNucleo.Escutando
            else -> EstadoNucleo.Repouso
        }
    }
}
