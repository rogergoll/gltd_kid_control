# Client — GLTD Kid Control

Aplicação que roda na máquina da criança (Linux Mint + Brave).

## O que faz
- Busca as listas de bloqueio/permissão no servidor (`GET /api/client/lists`).
- **Bloqueia navegadores não autorizados** para o usuário do perfil (mata o processo).
- **Reporta ao servidor** (`POST /api/client/report`): uso de aplicativos, URLs
  navegadas e histórico do YouTube (lidos do histórico do Brave).
- Fica **inativo** se o usuário logado na máquina for diferente do perfil.
- Roda como **daemon root** (systemd) — a criança não consegue matar/parar.
- Ícone de status na bandeja + notificações (sem opção de encerrar).

## Instalação
```bash
sudo dpkg -i gltd-kid-control-client_0.1.0_all.deb
sudo gltd-kid-client setup      # informa servidor, token do perfil e usuário
```

O `setup` grava `/etc/gltd-kid-control/client.json` e cria o autostart do ícone
na home da criança.

## Arquivos
- `/etc/gltd-kid-control/client.json` — configuração (root-only)
- `/run/gltd-kid-control/status.json` — status atual (lido pelo ícone)
- `/usr/share/gltd-kid-control/extension/` — extensão do Brave (YouTube)
- `/usr/share/applications/gltd-kid-control-client.desktop` — atalho no menu

## Testar manualmente
```bash
gltd-kid-client status    # mostra o status
gltd-kid-client once      # executa um ciclo (enforce + report)
gltd-kid-client daemon    # roda o daemon em primeiro plano
```
