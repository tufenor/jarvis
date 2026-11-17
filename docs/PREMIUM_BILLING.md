# Tufenor Video — Free e Premium

## Regras do produto

| Recurso | Free | Premium |
|---|---:|---:|
| Vídeos por lote | 50 | Sem limite configurado |
| Banner de anúncio | Sim | Não |
| Marca-d'água em lote | Disponível dentro do limite | Sem limite configurado |
| Agendamento | Disponível dentro do limite | Sem limite configurado |

## Produto da Play Store

O aplicativo espera a assinatura mensal:

```text
jarvis_premium_monthly
```

Esse produto ainda precisa ser criado no Play Console com preço, países,
período, política de cancelamento e textos de venda. Em APK instalado por ADB,
sem o produto publicado ou uma conta de teste licenciada, o app permanece no
plano Free.

## Segurança

O cliente consulta o Google Play Billing e reconhece compras válidas. Antes de
um lançamento comercial, o token deve ser enviado a um backend próprio para
verificação com a Google Play Developer API; o backend deve ser a fonte de
verdade do entitlement e dos cancelamentos. Nunca colocar credenciais de
serviço do Google no APK.

## Pendências de lançamento

- Criar `jarvis_premium_monthly` no Play Console.
- Testar compra, pendência, cancelamento, renovação e restauração no trilho
  interno.
- Adicionar backend de validação e Real-time Developer Notifications.
- Atualizar a política de privacidade e a seção Segurança dos dados para o SDK
  de anúncios e Billing.
