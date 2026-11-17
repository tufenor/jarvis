# FrequencyPost — avisos de terceiros e política de licenças

## Regra do projeto

O FrequencyPost será implementado com código próprio e dependências sob
licenças permissivas compatíveis com a distribuição pretendida, priorizando
MIT e Apache-2.0. A análise de Postiz, Postline, Mixpost e projetos similares
serve apenas como REA de arquitetura, fluxo e comportamento. Nenhum trecho
desses projetos é copiado para o APK.

Não incorporamos código GPL ou AGPL ao APK proprietário sem uma decisão de
licenciamento aprovada. Um aviso de terceiros não transforma uma dependência
copyleft em permissiva.

## Dependências a verificar antes da publicação

| Componente | Uso | Situação |
|---|---|---|
| AndroidX / Jetpack Compose | Interface e ciclo de vida | Verificar aviso Apache-2.0 na distribuição |
| Google Play Services / Billing | anúncios e compras | Verificar termos e avisos da versão distribuída |
| AndroidX Media3 | processamento de mídia | Verificar aviso Apache-2.0 na distribuição |
| `youtubedl-android` | download de mídia na variante interna `prototype` | **GPL-3.0: não é distribuído na variante `commercial`** |

O `youtubedl-android` não é usado como base para novos módulos de publicação.
O Gradle separa explicitamente as variantes: `prototype` é somente para testes
internos e inclui o motor copyleft; `commercial` não empacota o motor nem suas
bibliotecas nativas. Antes de uma distribuição comercial com download, o
backend oficial/licenciado precisa fornecer esse fluxo.

## Implementações próprias

Os módulos abaixo são código próprio do FrequencyPost e não são cópias de
Postiz, Postline, Mixpost ou outros agendadores:

- campanhas e jobs persistentes;
- idempotência e auditoria;
- compositor de múltiplos vídeos;
- agenda local;
- conectores oficiais por API;
- estados de publicação e tratamento de falhas.

## Procedimento para adicionar dependências

Antes de adicionar uma dependência:

1. registrar repositório e versão exata;
2. conferir o arquivo de licença e as dependências transitivas;
3. confirmar compatibilidade com o APK e o backend;
4. adicionar o aviso correspondente aqui;
5. executar uma verificação de licenças antes do release.

Este arquivo não substitui revisão jurídica da distribuição final.
