# Rotação de segredos do Terra.Ce

Política decidida em 29/09/2026: os segredos são trocados **uma vez por ano**, junto com a remoção das tags antigas no Docker Hub. Troque também, fora do calendário, sempre que houver suspeita de vazamento.

A primeira rotação deve acontecer logo depois da migração descrita abaixo, porque os valores atuais estão dentro das imagens `1.1.0` e `1.1.1`.

## Segredos

| Segredo | Quem usa | Onde fica em produção |
|---|---|---|
| `JWT_SECRET` | dashboard (`dfundce`) e miniserver (`tgdmserver`), com o mesmo valor | variável da stack no Portainer |
| `POSTGRES_PASSWORD` | Postgres e miniserver | variável da stack no Portainer |
| `CARTO_API_KEY` | dashboard | variável de ambiente do `dfundce` no Portainer |

No Portainer, cole sempre os valores **sem aspas**.

## Migração única: tirar o secrets.toml da imagem

Faça uma vez, antes da primeira rotação.

1. Atualize a stack no Portainer com o `docker-compose.stack.yml` do superprojeto. O serviço `dfundce` agora recebe `JWT_SECRET=${JWT_SECRET}`, a mesma variável que o `tgdmserver` já usa. Com a imagem atual isso não muda nada, porque o `secrets.toml` embutido ainda vence a variável.
2. Publique a imagem nova do dashboard com `./publish-docker.sh <versão>`. Ela não leva mais o `secrets.toml`, e o script pede confirmação do passo 1.
3. Reimplante o `dfundce` e abra as páginas de mapa. Se aparecer "Não foi possível carregar os dados", confira se `JWT_SECRET` está definido na stack.

## Rotação anual

1. **Gere os valores novos.**

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   Gere um valor para `JWT_SECRET` e outro para `POSTGRES_PASSWORD`.

2. **Troque a senha dentro do Postgres.** A variável `POSTGRES_PASSWORD` só vale na criação do banco. Com o banco já criado, a troca é feita por SQL:

   ```bash
   docker exec -it terrace-postgres psql -U terra -d geodata -c "ALTER USER terra WITH PASSWORD 'NOVA_SENHA';"
   ```

3. **Atualize as variáveis da stack** no Portainer: `JWT_SECRET` e `POSTGRES_PASSWORD`, sem aspas.

4. **Reimplante `tgdmserver` e `dfundce` juntos.** Enquanto só um dos dois estiver com o segredo novo, as consultas do dashboard recebem 401.

5. **Troque a `CARTO_API_KEY`**, se for o caso, no painel da CARTO (<https://carto.com/basemaps/apikey>). Mantenha a restrição ao domínio `terrace.virtual.ufc.br`.

6. **Apague as tags antigas no Docker Hub.** Em <https://hub.docker.com>, abra cada repositório (`dashboard-fundiario-ceara` e `terra-geodata-mini-server`), vá em *Tags* e apague todas as versões anteriores à atual. Confira também quem tem permissão de pull.

7. **Valide.**
   - Todas as páginas do dashboard carregam dados.
   - `GET /health` do miniserver responde `{"status": "healthy"}`.
   - Os logs do miniserver não mostram 401 depois do reimplante.

8. **Registre a rotação** na tabela abaixo e agende a próxima para daqui a um ano.

## Registro

| Data | Segredos trocados | Tags apagadas | Responsável |
|---|---|---|---|
| | | | |
