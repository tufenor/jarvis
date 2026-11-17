package com.jarvis.companion.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.jarvis.companion.R
import com.jarvis.companion.core.di.Services
import com.jarvis.companion.data.network.LoginOutcome
import com.jarvis.companion.ui.common.CoreMark
import com.jarvis.companion.ui.common.StatusChip
import com.jarvis.companion.ui.theme.NucleoAzul
import com.jarvis.companion.ui.theme.PerigoVermelho
import com.jarvis.companion.ui.theme.TextoSuave
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(
    services: Services,
    aoEntrar: () -> Unit,
    abrirServidor: () -> Unit,
) {
    val escopo = rememberCoroutineScope()
    var senha by remember { mutableStateOf("") }
    var erro by remember { mutableStateOf<String?>(null) }
    var enviando by remember { mutableStateOf(false) }
    val base by services.settings.state.collectAsState()

    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(24.dp))
        CoreMark()
        Text("J.A.R.V.I.S.", style = MaterialTheme.typography.displayMedium, color = NucleoAzul)
        Text(stringResource(R.string.login_title), style = MaterialTheme.typography.titleMedium)
        StatusChip(base.baseUrl.ifBlank { "SEM SERVIDOR" }, cor = TextoSuave)

        OutlinedTextField(
            value = senha, onValueChange = { senha = it },
            label = { Text(stringResource(R.string.login_hint)) },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth(),
        )

        erro?.let { Text(it, color = PerigoVermelho, style = MaterialTheme.typography.bodyMedium) }

        Button(
            onClick = {
                if (senha.isBlank() || enviando) return@Button
                enviando = true; erro = null
                escopo.launch {
                    val resultado = runCatching { services.auth.entrar(senha) }
                        .getOrElse { LoginOutcome.Erro(it.message ?: "sem conexão") }
                    enviando = false
                    when (resultado) {
                        LoginOutcome.Ok -> aoEntrar()
                        LoginOutcome.SenhaErrada -> erro = "Senha errada."
                        LoginOutcome.SemSenha -> erro = "O JARVIS ainda não tem senha configurada."
                        is LoginOutcome.Erro -> erro = resultado.mensagem
                    }
                }
            },
            modifier = Modifier.fillMaxWidth(),
            enabled = !enviando && base.baseUrl.isNotBlank(),
        ) { Text(stringResource(R.string.login_button)) }

        TextButton(onClick = abrirServidor) { Text(stringResource(R.string.settings_title)) }
    }
}
