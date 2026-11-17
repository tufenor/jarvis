package com.jarvis.companion.ui.diagnostics

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.jarvis.companion.R
import com.jarvis.companion.core.di.Services
import com.jarvis.companion.ui.theme.Fundo
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DiagnosticsScreen(services: Services, voltar: () -> Unit) {
    val escopo = rememberCoroutineScope()
    val conexao by services.channel.conexao.collectAsState()
    val retrato by services.channel.ultimo.collectAsState()
    val cfg by services.settings.state.collectAsState()
    var pong by remember { mutableStateOf<String?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.diag_title)) },
                navigationIcon = {
                    IconButton(onClick = voltar) {
                        Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = "Voltar")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Fundo),
            )
        },
        containerColor = Fundo,
    ) { padding ->
        Column(
            modifier = Modifier.padding(padding).padding(16.dp).fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Endereço: ${cfg.baseUrl.ifBlank { "(não configurado)" }}")
            Text("Aparelho: ${cfg.deviceName}")
            Text("Canal: $conexao")
            Text("Cérebro: ${retrato?.cerebro?.nome ?: "—"} (online=${retrato?.cerebro?.online ?: "?"})")
            Text("CPU: ${retrato?.sistema?.cpu ?: "—"}  Mem: ${retrato?.sistema?.memoria ?: "—"}")
            Button(onClick = {
                escopo.launch {
                    pong = if (services.api.saude()) "/api/saude respondeu OK"
                           else "sem resposta — verifique o endereço e o Tailscale"
                }
            }, modifier = Modifier.fillMaxWidth()) { Text("TESTAR CONEXÃO") }
            pong?.let { Text(it) }
        }
    }
}
