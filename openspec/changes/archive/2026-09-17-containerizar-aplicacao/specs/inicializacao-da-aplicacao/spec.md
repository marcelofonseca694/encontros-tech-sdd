## Purpose

Define o que a aplicação exige do ambiente para iniciar, o que ela deixa de fazer durante a inicialização, e como se comporta quando a dependência de banco de dados está ausente ou volta a ficar disponível.

## ADDED Requirements

### Requirement: Segredo de aplicação obrigatório e externo

A aplicação SHALL obter seu segredo de aplicação exclusivamente do ambiente, sem valor padrão embutido no código-fonte. Na ausência do segredo, a aplicação SHALL NOT iniciar.

#### Scenario: Segredo ausente no ambiente

- **WHEN** a aplicação é iniciada sem que o segredo de aplicação esteja definido no ambiente
- **THEN** a aplicação não inicia, e a causa fica registrada de forma que permita a quem executou identificar a variável ausente

#### Scenario: Segredo fornecido pelo ambiente

- **WHEN** a aplicação é iniciada com o segredo de aplicação definido no ambiente
- **THEN** a aplicação inicia normalmente e utiliza o valor fornecido

#### Scenario: Segredo no código-fonte

- **WHEN** o código-fonte da aplicação é inspecionado
- **THEN** nenhum valor de segredo de aplicação utilizável está presente

### Requirement: Endereço e credenciais do banco vêm do ambiente

A aplicação SHALL obter o endereço e as credenciais do banco de dados do ambiente, nunca de valores fixados no código-fonte ou na imagem.

#### Scenario: Apontar a aplicação para outro banco

- **WHEN** o endereço do banco é alterado no ambiente e a aplicação é reiniciada
- **THEN** a aplicação passa a usar o novo endereço, sem que a imagem seja reconstruída

### Requirement: Indisponibilidade do banco não impede a inicialização

A indisponibilidade do banco de dados SHALL NOT impedir a aplicação de iniciar nem encerrar o processo em execução.

#### Scenario: Início com o banco parado

- **WHEN** a aplicação é iniciada e o banco de dados está indisponível
- **THEN** o processo inicia e permanece em execução, sem encerrar

#### Scenario: Banco cai com a aplicação em execução

- **WHEN** o banco de dados se torna indisponível enquanto a aplicação atende requisições
- **THEN** o processo permanece em execução

### Requirement: Recuperação da dependência sem reinício

Quando o banco de dados volta a ficar disponível, ou quando seu endereço de rede muda mantendo o mesmo endereço de conexão, a aplicação SHALL voltar a atender requisições de negócio sem que o processo precise ser reiniciado.

#### Scenario: Banco retorna após indisponibilidade

- **WHEN** o banco de dados volta a ficar disponível depois de um período fora
- **THEN** as requisições de negócio seguintes são atendidas normalmente, sem reiniciar a aplicação

#### Scenario: Conexões mortas após troca de endereço de rede

- **WHEN** o endereço de rede do banco muda e as conexões previamente abertas deixam de ser utilizáveis
- **THEN** as conexões inutilizáveis são descartadas antes do uso, e a aplicação não serve erro depois de a dependência já ter se recuperado
