# Arquitetura — GLTD Kid Control Server

## Componentes

```
gltd_kid_server/
├── __main__.py    CLI (argumentos, load config)
├── config.py      ServerConfig + load/save JSON + caminhos padrão
├── models.py      dataclasses: ChannelEntry, Profile, HistoryEntry
├── lists.py       leitura/validação dos CSVs (block/allow)
├── db.py          Store (interface) + MariaDBStore (PyMySQL) + JsonStore (fallback)
├── api.py         KidControlServer (ThreadingHTTPServer) + endpoints
└── web/index.html UI estática que consome a API
```

## Fluxo de dados

1. O admin edita `config.json` (ou usa a Web UI futura) para definir perfis.
2. `lists/` contém os CSVs de bloqueio/permissão — fonte de dados real.
3. Os **clients** (máquinas das crianças) chamam a API para:
   - baixar as listas do seu perfil (`/api/profiles/{id}`);
   - reportar vídeos assistidos (`POST /api/history`).
4. O admin acompanha tudo pela Web UI (`/`) e pelo histórico (`/api/history`).

## Decisões

- **HTTP stdlib**: sem Flask/FastAPI — `http.server` com handler JSON simples.
- **MariaDB** para dados (perfis, histórico, uso de apps, urls) via PyMySQL.
  Fallback **JSON** em arquivos no `data_dir` (sem MariaDB).
- Config em **JSON** em `/etc/gltd-kid-control/config.json` (produção) ou
  `config/server.example.json` (desenvolvimento).

## Extensões futuras

- **DNS local** no server (ex.: via dnsmasq) para bloquear navegação dos
  clients sem contato com o server.
- **Autenticação** da API (token por cliente) — hoje a API é aberta na LAN.
- Persistir novos filtros/canais adicionados pela Web UI de volta nos CSVs.
