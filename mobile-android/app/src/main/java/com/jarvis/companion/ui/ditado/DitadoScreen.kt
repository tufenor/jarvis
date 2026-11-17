package com.jarvis.companion.ui.ditado

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.ContentCopy
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material.icons.outlined.MicOff
import androidx.compose.material.icons.outlined.Share
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.companion.core.di.Services
import com.jarvis.companion.data.voz.ModeloVosk
import com.jarvis.companion.data.voz.VoskDitado
import com.jarvis.companion.ui.common.BackgroundHud
import com.jarvis.companion.ui.common.GlassCard
import com.jarvis.companion.ui.theme.*
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DitadoScreen(services: Services, voltar: () -> Unit) {
    val ctx = LocalContext.current
    val escopo = rememberCoroutineScope()

    val modelo = remember { ModeloVosk(ctx) }
    var baixando by remember { mutableStateOf(false) }
    var progresso by remember { mutableIntStateOf(0) }
    var erro by remember { mutableStateOf<String?>(null) }
    var modeloPronto by remember { mutableStateOf(modelo.jaBaixado()) }

    val ditado = remember { VoskDitado(ctx) }
    val parcial by ditado.parcial.collectAsState()
    val finalizado by ditado.finalizado.collectAsState()
    var ouvindo by remember { mutableStateOf(false) }

    val micPerm = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) {
            ouvindo = true
            escopo.launch {
                try { ditado.iniciar(modelo.pasta.absolutePath) }
                catch (t: Throwable) { erro = t.message; ouvindo = false }
            }
        } else erro = "Permissao de microfone recusada."
    }

    Box(Modifier.fillMaxSize()) {
        BackgroundHud()
        Scaffold(
            containerColor = androidx.compose.ui.graphics.Color.Transparent,
            topBar = {
                TopAppBar(
                    title = {
                        Text("DITADO OFFLINE",
                            style = MaterialTheme.typography.titleLarge.copy(
                                fontFamily = FontFamily.Monospace, letterSpacing = 3.sp, fontSize = 14.sp,
                            ),
                            color = Texto)
                    },
                    navigationIcon = {
                        IconButton(onClick = voltar) {
                            Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = "Voltar", tint = Texto)
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = androidx.compose.ui.graphics.Color.Transparent,
                    ),
                )
            },
        ) { padding ->
            Column(
                modifier = Modifier.padding(padding).padding(16.dp).fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                if (!modeloPronto) {
                    BlocoBaixar(
                        baixando = baixando, progresso = progresso, erro = erro,
                        aoBaixar = {
                            baixando = true; erro = null
                            escopo.launch {
                                modelo.baixarSePreciso()
                                    .catch { t -> erro = t.message; baixando = false }
                                    .collect { p ->
                                        if (p < 0) {
                                            baixando = false; modeloPronto = true
                                        } else progresso = p
                                    }
                            }
                        },
                    )
                } else {
                    BlocoDitado(
                        parcial = parcial,
                        finalizado = finalizado,
                        ouvindo = ouvindo,
                        iniciar = {
                            erro = null
                            micPerm.launch(Manifest.permission.RECORD_AUDIO)
                        },
                        parar = {
                            escopo.launch {
                                ditado.parar()
                                ouvindo = false
                            }
                        },
                        limpar = { ditado.limpar() },
                        copiar = {
                            val cm = ctx.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                            cm.setPrimaryClip(ClipData.newPlainText("ditado", finalizado))
                        },
                        compartilhar = {
                            val i = Intent(Intent.ACTION_SEND).apply {
                                type = "text/plain"
                                putExtra(Intent.EXTRA_TEXT, finalizado)
                            }
                            ctx.startActivity(Intent.createChooser(i, "Enviar transcricao"))
                        },
                    )
                    Text(
                        "Modelo em ${modelo.pasta.absolutePath}",
                        style = MaterialTheme.typography.labelMedium.copy(
                            fontFamily = FontFamily.Monospace, fontSize = 9.sp),
                        color = TextoAtenuado,
                    )
                    TextButton(onClick = {
                        modelo.apagar()
                        modeloPronto = false
                    }) {
                        Text("Apagar modelo (" + ModeloVosk.TAMANHO_ESTIMADO_MB + " MB)", color = TextoSuave)
                    }
                }
                erro?.let {
                    Text(it, color = PerigoVermelho, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

@Composable
private fun BlocoBaixar(
    baixando: Boolean, progresso: Int, erro: String?,
    aoBaixar: () -> Unit,
) {
    GlassCard(corBorda = NucleoAzul.copy(alpha = 0.5f)) {
        Text("MODELO PT-BR", style = MaterialTheme.typography.labelLarge.copy(
            fontFamily = FontFamily.Monospace, letterSpacing = 2.sp,
        ), color = NucleoAzul)
        Spacer(Modifier.height(10.dp))
        Text(
            "Precisa baixar uma unica vez o modelo Vosk portugues-BR (~${ModeloVosk.TAMANHO_ESTIMADO_MB} MB). " +
            "Depois o ditado funciona 100% offline, sem enviar seu audio para servidor nenhum. " +
            "Fonte: alphacephei.com (Apache-2.0).",
            style = MaterialTheme.typography.bodyMedium, color = Texto,
        )
        Spacer(Modifier.height(16.dp))
        if (baixando) {
            LinearProgressIndicator(
                progress = { progresso / 100f },
                modifier = Modifier.fillMaxWidth(),
                color = NucleoAzul,
                trackColor = Superficie,
            )
            Spacer(Modifier.height(6.dp))
            Text("$progresso%", color = TextoSuave, style = MaterialTheme.typography.labelMedium)
        } else {
            Button(
                onClick = aoBaixar, modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(containerColor = NucleoAzul, contentColor = Fundo),
            ) {
                Text("BAIXAR MODELO", style = MaterialTheme.typography.labelLarge.copy(
                    fontFamily = FontFamily.Monospace, letterSpacing = 2.sp))
            }
        }
    }
}

@Composable
private fun BlocoDitado(
    parcial: String, finalizado: String,
    ouvindo: Boolean,
    iniciar: () -> Unit, parar: () -> Unit,
    limpar: () -> Unit, copiar: () -> Unit, compartilhar: () -> Unit,
) {
    GlassCard(corBorda = (if (ouvindo) NucleoMagenta else NucleoAzul).copy(alpha = 0.5f)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            FilledIconButton(
                onClick = { if (ouvindo) parar() else iniciar() },
                colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = if (ouvindo) NucleoMagenta else NucleoAzul,
                    contentColor = Fundo,
                ),
                modifier = Modifier.size(64.dp),
            ) {
                Icon(if (ouvindo) Icons.Outlined.MicOff else Icons.Outlined.Mic,
                    contentDescription = if (ouvindo) "Parar" else "Ouvir",
                    modifier = Modifier.size(32.dp))
            }
            Spacer(Modifier.width(16.dp))
            Column {
                Text(
                    if (ouvindo) "OUVINDO" else "TOQUE PARA DITAR",
                    style = MaterialTheme.typography.labelLarge.copy(
                        fontFamily = FontFamily.Monospace, letterSpacing = 2.sp),
                    color = if (ouvindo) NucleoMagenta else NucleoAzul,
                )
                Text(
                    "Reconhecimento 100% local",
                    style = MaterialTheme.typography.bodySmall, color = TextoSuave,
                )
            }
        }
    }

    Spacer(Modifier.height(12.dp))

    GlassCard(corBorda = Contorno) {
        Text("TRANSCRICAO", style = MaterialTheme.typography.labelLarge.copy(
            fontFamily = FontFamily.Monospace, letterSpacing = 2.sp), color = TextoSuave)
        Spacer(Modifier.height(10.dp))
        Column(Modifier.heightIn(min = 120.dp)) {
            if (finalizado.isNotBlank()) {
                Text(finalizado, color = Texto, style = MaterialTheme.typography.bodyLarge)
            }
            if (parcial.isNotBlank()) {
                Spacer(Modifier.height(4.dp))
                Text(parcial, color = TextoSuave, style = MaterialTheme.typography.bodyMedium)
            }
            if (finalizado.isBlank() && parcial.isBlank()) {
                Text("A transcricao aparece aqui conforme voce fala.",
                    color = TextoAtenuado, style = MaterialTheme.typography.bodyMedium)
            }
        }
        Spacer(Modifier.height(12.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = copiar, enabled = finalizado.isNotBlank(),
                modifier = Modifier.weight(1f)) {
                Icon(Icons.Outlined.ContentCopy, contentDescription = null, modifier = Modifier.size(16.dp))
                Spacer(Modifier.width(6.dp)); Text("COPIAR")
            }
            OutlinedButton(onClick = compartilhar, enabled = finalizado.isNotBlank(),
                modifier = Modifier.weight(1f)) {
                Icon(Icons.Outlined.Share, contentDescription = null, modifier = Modifier.size(16.dp))
                Spacer(Modifier.width(6.dp)); Text("ENVIAR")
            }
            OutlinedButton(onClick = limpar) {
                Icon(Icons.Outlined.Delete, contentDescription = "Limpar", modifier = Modifier.size(16.dp))
            }
        }
    }
}
