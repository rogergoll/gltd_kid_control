# Empacotamento — GLTD Kid Control Server

## Gerar o .deb
```bash
bash server/scripts/build_deb.sh
```
Gera `dist/gltd-kid-control-server_0.1.0_all.deb`.

## Conteúdo do pacote
- `/usr/lib/gltd-kid-control/gltd_kid_server/` — código Python
- `/usr/share/gltd-kid-control/lists/` — listas CSV
- `/usr/share/gltd-kid-control/config/` — config de exemplo
- `/usr/bin/gltd-kid-server` — entrypoint

## Pós-instalação (a implementar)
O `postinst` deve:
1. criar `/var/lib/gltd-kid-control`;
2. rodar o `first_run.py` (senha root + server/client).

## Dependências
- `python3` (>= 3.10)
- `mariadb-server`, `mariadb-client` — banco de dados (padrão)
- `python3-pymysql` — driver Python do MariaDB/MySQL

## Banco de dados
- **MariaDB** (padrão): banco `gltd_kcontrol`, usuário `gltd_kcontrol_app@localhost`.
  O schema está em `server/sql/schema.sql`.
- **JSON** (fallback, opcional na instalação): arquivos em `data_dir`
  (`profiles.json`, `history/<data>.json`, `usage/<data>.json`, `urls/<data>.json`).
