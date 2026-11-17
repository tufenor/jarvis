package com.jarvis.companion.ui.settings

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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(services: Services, voltar: () -> Unit) {
    val atual by services.settings.state.collectAsState()
    var url by remember { mutableStateOf(atual.baseUrl) }
    var nome by remember { mutableStateOf(atual.deviceName) }
    var operador by remember { mutableStateOf(atual.operatorName) }
    var saver by remember { mutableStateOf(atual.batterySaver) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.settings_title)) },
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
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            OutlinedTextField(
                value = url, onValueChange = { url = it },
                label = { Text(stringResource(R.string.settings_base_url)) },
                placeholder = { Text("https://seu-servidor:8080") },
                singleLine = true, modifier = Modifier.fillMaxWidth(),
                supportingText = { Text("Use seu endereço Tailscale quando estiver fora de casa.") },
            )
            OutlinedTextField(
                value = nome, onValueChange = { nome = it },
                label = { Text(stringResource(R.string.settings_device_name)) },
                singleLine = true, modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = operador, onValueChange = { operador = it },
                label = { Text("Como o JARVIS deve te chamar") },
                placeholder = { Text("SENHOR") },
                supportingText = { Text("Aparece na saudação do painel. Use seu nome ou um título.") },
                singleLine = true, modifier = Modifier.fillMaxWidth(),
            )
            Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Switch(checked = saver, onCheckedChange = { saver = it })
                Spacer(Modifier.width(12.dp))
                Text(stringResource(R.string.settings_battery_saver))
            }
            Button(
                onClick = {
                    services.settings.updateBaseUrl(url)
                    services.settings.updateDeviceName(nome)
                    services.settings.updateOperatorName(operador)
                    services.settings.updateBatterySaver(saver)
                    voltar()
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text(stringResource(R.string.settings_save)) }
        }
    }
}
