### **3.2. Estrutura do DDC Interno **

A função PID combina toda a lógica necessária para realizar o processamento de canais de entrada analógica, controle proporcional-integral-derivativo (PID).

O bloco de função PID suporta controle de modo, escalonamento e limitação de sinais, controle feedforward, seguimento por override e detecção de limites de alarme. Para suporte a testes, é possível habilitar a simulação, permitindo que o valor de medição e seu status sejam fornecidos manualmente ou por outro bloco através da entrada *SIMULATE_IN*.

No modo Cascata (Cas), o setpoint (SP) é ajustado por um controlador mestre. No modo Automático (Auto), o SP pode ser ajustado pelo operador. Em ambos os modos (Cas e Auto), a saída é calculada utilizando uma equação PID padrão. No modo Manual (Man), a saída do bloco é definida pelo operador, escrevendo diratamente na variável CO. O PID também possui dois modos remotos, RCas e ROut, que são semelhantes aos modos Cas e Man, respectivamente, porém o SP e o OUT são fornecidos por um programa supervisório remoto, para isso duas variaveis de entrada devem ser criadas para o PID, *RCAS_IN* e *ROUT_IN*.

Você pode conectar a entrada de tracking (*TRK_VAL*) para permitir tracking externo da saída, ou seja, quando o PID estiver no modo LOCAL OVERRIDE que é acionado pela entrada *TRK_IN_D*, o valor da saída será igual ao valor encontrado em *TRK_VAL*. 

Outras variáveis de entrada da função PID:

CAS_IN é o valor de SP remoto proveniente de sistemas externos, este valor será lido do servidor OPC-UA.
FF_VAL é o valor e status da entrada de controle feedforward, proveniente de sistemas externos, este valor será lido do servidor OPC-UA.
IN é a conexão para a variável de processo (PV) proveniente, proveniente de sistemas externos, este valor será lido do servidor OPC-UA. 
SIMULATE_IN é o valor e status de entrada utilizados pelo bloco no lugar da medição analógica quando a simulação está habilitada. O usuário poderá escrever nessa variável para simular um valor de PV para testes.
TRK_IN_D inicia a função de de tracking externo, sinal proveniente de sistemas externos, este valor será lido do servidor OPC-UA.
TRK_VAL é o valor, após escalonamento, aplicado à saída (OUT). É proveniente de sistemas externos, este valor será lido do servidor OPC-UA.
OUT é o valor de saída do bloco e seu respectivo status.

* **Escalonamento:** 0-100% obrigatório. Deverá existir um parâmetro onde o usuário irá definir a escala (minimo e maximo) da PV e da saída do OUT 
* **Unidades:** $K_p$ (Ganho), $T_i$ (Tempo Integral em *Segundos/Repetição*), $T_d$ (Tempo Derivativo em Segundos).
* **Equação na Forma de Velocidade (Derivative on PV):** Para evitar "Derivative Kick" e garantir Transferência Bumpless:
  $$\Delta CV = Gain \cdot \left[ (e_n - e_{n-1}) + \frac{\Delta t}{Reset} \cdot e_n - Rate \cdot \left( \frac{PV_n - 2PV_{n-1} + PV_{n-2}}{\Delta t} \right) \right]$$
  $$CV_{nova} = CV_{atual} + \Delta CV$$
* **Filtro Derivativo:** Inclui filtro passa-baixa obrigatório: $Filtro = \frac{Rate}{8}$.
* **MODOS DE OPERAÇÃO**x: 
Aqui está uma descrição resumida de cada um dos modos de operação suportados pelo bloco de função PID:
-   **Out of Service (OOS):** O algoritmo do bloco não está ativo. A saída é mantida no seu último valor conhecido ou é levada para um valor de ação de falha pré-especificado.
-   **Initializing Manual (IMan):** Utilizado em malhas de controle em cascata. O bloco mestre (a montante) é colocado neste modo quando o bloco escravo (a jusante) sai do modo de cascata, impedindo que o bloco mestre feche a malha. O bloco sai do modo IMan quando o bloco escravo retorna para os modos Cas ou RCas.
-   **Local Override (LO):** O bloco entra neste modo quando a função de rastreamento (*tracking*) é ativada. A saída do bloco passa a ser forçada a um valor diferente daquele que seria gerado pela sua execução normal. 
-   **Manual (Man):** A saída do bloco é definida e controlada diretamente pelo operador.
-   **Automatic (Auto):** O algoritmo de controle do bloco fica ativo e a saída é calculada com base em um *setpoint* inserido pelo próprio operador.
-   **Cascade (Cas):** Funciona de forma semelhante ao modo Automático, mas o *setpoint* é fornecido automaticamente por outro bloco de função através da entrada `CAS_IN`. O bloco também calcula um valor de retrocálculo (`BKCAL_OUT`) para garantir uma transferência de modo sem solavancos (*bumpless transfer*).
-   **Remote Cascade (RCas):** Semelhante ao modo Cascata, mas o *setpoint* é fornecido por um programa de controle externo através do parâmetro `RCAS_IN`.
-   **Remote Out (ROut):** Semelhante ao modo Manual, mas o valor da saída (`OUT`) é fornecido por um programa de controle externo através do parâmetro `ROUT_IN`, em vez de ser inserido diretamente pelo operador.


### A tabela a seguir lista os parâmetros de sistema para o bloco de função PID:

| Parâmetro | Unidades | Descrição |
|----------|----------|----------|
| ABNORM_ACTIVE | Nenhuma | Indica que uma condição de erro da execução do modulo do PID. |
| ALARM_HYS | Percentual | Quantidade que o valor de alarme deve retornar para dentro do limite antes que a condição ativa de alarme associada seja limpa. ALARM_HYS é limitado a 50% da escala. |
| ALERT_KEY | Nenhuma | Número de identificação atribuído pelo usuário, reportado nas mensagens de alarme do bloco, que permite que aplicações de HMI classifiquem e filtrem alarmes e eventos. Defina este parâmetro para cada bloco de função para indicar a unidade física associada. Essa informação pode ser usada no sistema host para classificação de alarmes, entre outros. |
| ALPHA | Nenhuma | Fator de filtro para a ação derivativa. O valor padrão é 0,125. A faixa válida em tempo de execução é de 0,05 a 1,0. Aumentar ALPHA aumenta o amortecimento da ação derivativa. Ajustar ALPHA pode impactar a proteção contra ruído quando RATE é utilizado. Por isso, normalmente ALPHA NÃO deve ser alterado. |
| ARW_HI_LIM | OUT | Limite superior de Anti-Reset Windup. Quando a saída ultrapassa ARW_HI_LIM e a ação integral está retornando ao limite, o tempo de RESET aplicado é reduzido por um fator de 16. Insira um valor entre OUT_HI_LIM e OUT_LO_LIM. |
| ARW_LO_LIM | OUT | Limite inferior de Anti-Reset Windup. Quando a saída ultrapassa ARW_LO_LIM e a ação integral está retornando ao limite, o tempo de RESET aplicado é reduzido por um fator de 16. Insira um valor entre OUT_HI_LIM e OUT_LO_LIM. |
| BAD_ACTIVE | Nenhuma | Indica que uma condição de erro do bloco selecionada em BAD_MASK está verdadeira (ativa). |
| BAD_MASK | Nenhuma | Conjunto de condições de erro ativas que acionam uma condição Bad definida pelo usuário. O usuário seleciona um subconjunto das condições de erro do bloco (BLOCK_ERR) no parâmetro BAD_MASK. Quando qualquer dessas condições é verdadeira, BAD_ACTIVE torna-se verdadeiro. Quando qualquer condição de BLOCK_ERR não incluída em BAD_MASK é verdadeira, ABNORM_ACTIVE torna-se verdadeiro. |

| BLOCK_ERR | Nenhuma | Resumo das condições de erro ativas associadas ao bloco. Os erros possíveis são: Out of Service; Readback Failed; Output Failure; Input Failure/Bad PV; Local Override; Simulate Active |
| BYPASS | Nenhuma | Quando habilitado e o bloco está em AUTO, CAS ou RCAS, ignora o algoritmo de controle e transfere o SP (em %) diretamente para OUT. Em modo MAN, OUT é copiado para SP. Quando desabilitado, o bloco opera normalmente. Para ativar/desativar, selecione Bypass Enable em CONTROL_OPTS e coloque o bloco em modo MAN. |
| CAS_IN | mesma unidade de engenharia e limites da PV definidos em PV_SCALE | Valor de setpoint analógico remoto de outro bloco. Se o status de CAS_IN for Bad e o modo alvo for CAS, o modo real do PID muda para o modo permitido superior, normalmente AUTO ou MAN. |
| CONTROL_OPTS | Nenhuma | Permite configurar opções de controle. As opções são: No OUT limits in Manual; Obey SP lim if Cas or RCas; Use PV for BKCAL_OUT; Track in Manual; Track Enable; Direct Acting; SP Track retained target; SP-PV Track in LO or IMan; SP-PV Track in ROut; SP-PV Track in Man; Bypass Enable |
| DV_HI_ACT | Nenhuma | Resultado da detecção de alarme associado a DV_HI_LIM. Se DV_HI_ACT = True, DV_HI_LIM foi excedido. |
| DV_HI_LIM | mesma unidade de engenharia e limites da PV definidos em PV_SCALE | Quantidade que PV pode exceder SP antes de gerar alarme de desvio alto. Não pode ser maior que a faixa de PV_SCALE. |
| DV_LO_ACT | Nenhuma | Resultado da detecção de alarme associado a DV_LO_LIM. Se DV_LO_ACT = True, DV_LO_LIM foi excedido. |
| DV_LO_LIM | mesma unidade de engenharia e limites da PV definidos em PV_SCALE | Quantidade que PV pode ficar abaixo de SP antes de gerar alarme de desvio baixo. DV_LO_LIM é negativo e comparado com (PV – SP). |
| ENABLE_OPTIMIZER | Nenhuma | Habilita/desabilita o otimizador. |
| ERROR |  mesma unidade de engenharia da PV | Diferença entre SP e PV. |
| FF_ENABLE | Nenhuma | Habilita/desabilita feedforward. |
| FF_GAIN | Nenhuma | O valor do ganho de feedforward. FF_VAL é multiplicado por FF_GAIN antes de ser adicionado à saída de controle calculada. |
| FF_SCALE | Nenhuma | Os valores de escala superior e inferior, o código de unidades de engenharia e o número de dígitos à direita da vírgula decimal associados ao valor de feedforward (FF_VAL). |
| FF_VAL |  unidade de engenharia definida em FF_SCALE | O valor e da entrada de controle de feedforward. |
| GAIN | Nenhuma | Ganho proporcional. |
| HI_ACT | Nenhuma | resultado da detecção de alarme associada a HI_LIM. Se HI_ACT for igual a Verdadeiro, HI_LIM foi excedido. |
| HI_HI_ACT | Nenhuma | O resultado da detecção de alarme associada a HI_HI_LIM. Se HI_HI_ACT for igual a Verdadeiro, HI_HI_LIM foi excedido.|
| HI_HI_LIM | mesma unidade de engenharia e limites da PV definidos em PV_SCALE | O resultado da detecção de alarme associada a HI_HI_LIM. Se HI_HI_ACT for igual a Verdadeiro, HI_HI_LIM foi excedido.|
| HI_LIM | mesma unidade de engenharia e limites da PV definidos em PV_SCALE | A configuração para o limite de alarme usado para detectar a condição de alarme de nível alto. |
| IDEADBAND) | mesma unidade de engenharia e limites da PV definidos em PV_SCALE | O valor da banda morta. Quando o erro entra em IDEADBAND, a ação integral para. As ações proporcional e derivativa continuam.|
| IN | mesma unidade de engenharia e limites da PV definidos em PV_SCALE | O valor da entrada analógica (PV). |

| IO_OPTS | Nenhuma | Opções de I/O: estão definidas na sessão **IO_OPTS**. |

| LO_ACT | Nenhuma | O resultado da detecção de alarme associada a LO_LIM. Se LO_ACT for igual a Verdadeiro, LO_LIM foi excedido. |
| LO_LIM | mesma unidade de engenharia e limites da PV definidos em PV_SCALE | configuração para o limite de alarme usado para detectar a condição de alarme baixo. |
| LO_LO_ACT | Nenhuma | resultado da detecção de alarme associada a LO_LO_LIM. Se LO_LO_ACT for igual a Verdadeiro, LO_LO_LIM foi excedido.|
| LO_LO_LIM | mesma unidade de engenharia e limites da PV definidos em PV_SCALE |  configuração para o limite de alarme usado para detectar a condição de alarme de nível muito baixo. |
| LOW_CUT | mesma unidade de engenharia e limites da PV definidos em PV_SCALE | Ativado quando a opção de E/S de Corte Inferior está habilitada. Quando a medição convertida estiver abaixo do valor LOW_CUT, o PV é definido como 0,0. |

| MODE | Nenhuma | Parâmetro usado para mostrar e definir o estado de operação do bloco. MODE contém os subparametros MODE_ACTUAL, MODE_TARGET, os possíveis modos permitidos (selecionados via checkbox pelo usuário) e MODE_NORMAL que armazena qual modo este controlador normalmente deve operar. |
| OPTIMIZER | Nenhuma | Variável que armazena qual técnica de otimização o operador escolheu  |
| OUT | mesma unidade de engenharia e limites da OUT definidos em OUT_SCALE | Saída do bloco. |
| OUT_HI_LIM | mesma unidade de engenharia e limites da OUT definidos em OUT_SCALE | Limite máximo da saída. |
| OUT_LO_LIM | mesma unidade de engenharia e limites da OUT definidos em OUT_SCALE | Limite mínimo da saída. |

| OUT_SCALE | Nenhuma | Escala da saída, valores mínimo e máximo dessa variável. |

| PROCESS_TYPE | Nenhuma | Tipo de processo: auto-regulado (estabiliza sozinho em manual) ou integrador (processo instável). |

| PV | unidade de engenharia e limites PV_SCALE | Variável de processo usada na execução do bloco e na detecção do limite de alarme. Nota: Um bloco PID não será integrado se o status do limite de PV for CONSTANTE. |
| PV_FTIME | Segundos | Constante de tempo do filtro de primeira ordem, filtro esse aplicado a PV antes do sinal ser pwrocessado pelo algortimo PID. |
| PV_SCALE | Nenhuma | Armazena qual é a unidade de engenharia da PV, seu valor minimo e máximo. |
| RATE | Segundos | Constante de tempo da ação derivativa, tempo derivativo T_d.|

| RCAS_IN | unidade de engenharia e limites SP_SCALE | Valor e status do ponto de ajuste analógico remoto. Entrada fornecida por um dispositivo ou a saída de outro bloco. |

| RESET | Segundos por repetição | A constante de tempo integral da ação, é o tempo integral T_i. |
| ROUT_IN | unidade de engenharia e limites  de OUT_SCALE | Valor e status da saída remota. Entrada fornecida por um sistema externo, valor lido do servidor OPC-UA para uso como saída (modo ROut). |
| ROUT_OUT | unidade de engenharia e limites de OUT_SCALE | A saída fornecida pela variável de entrada de ROUT_IN.  |

| SHED_OPT | Nenhuma | Ação em perda de comunicação com o servidor OPC-UA. Aqui o usuário deverá definir se o controle continua em AUTO, vai para MANUAL ou modo Out of Service. |
| SHED_TIME | Segundos | Tempo máximo de timeout. |
| SIMULATE | boolean | Habilita simulação. |
| SIMULATE_IN | unidade de engenharia e limites de PV_SCALE | Entrada de simulação. Substitui a PV para ser utilizada no calculo do algoritmo PID |
| SP | unidade de engenharia e limites  de PV_SCALE | Setpoint. |
| SP_FTIME | Segundos | Constante de tempo do filtro SP de primeira ordem, aplicado nas mudansças do valor de SP. |
| SP_HI_LIM | unidade de engenharia e limites  de PV_SCALE | Limite superior do SP. |
| SP_LO_LIM | unidade de engenharia e limites  de PV_SCALE | Limite inferior do SP. |
| SP_RATE_DN | (unidade de engenharia@)/s | Taxa de rampa na qual as alterações de ponto de ajuste para baixo são aplicadas no modo Automático, em unidades de engenharia da PV por segundo. Se a taxa de rampa for definida como 0,0, o valor do SP será usado imediatamente. |

| SP_RATE_UP | EU/s | Taxa de rampa na qual as alterações de ponto de ajuste para cima são aplicadas no modo Automático, em unidades de engenharia da PV por segundo. Se a taxa de rampa for definida como 0,0, o valor do SP será usado imediatamente. |

| SP_WRK | unidade de engenharia e limites  de PV_SCALE | Setpoint de trabalho, aquele efetivamente enviado ao algoritmo PID. Valor do SP sujeito as regras impostas por SP_RATE_DN e SP_RATE_UP.  |


| TRACK_OPT | Nenhuma | Opção de Rastreamento. Permite selecionar o comportamento do *tracking* quando o status de TRK_IN_D for Bad (bad quality vindo do servidor OPC-UA@). As três opções de rastreamento são:

Sempre Usar Valor - O bloco reage ao valor atual de TRK_IN_D, independentemente do status.

Usar Último Valor Válido - O bloco usa o valor de TRK_IN_D da última vez em que seu status não foi *Bad*. Este é o valor padrão para TRACK_OPT. 

Track se Bad - Se o status de TRK_IN_D for Bad, o algoritmo reage como se o valor de TRK_IN_D fosse True (1), mesmo que o valor seja False (0). |
| TRK_IN_D | boolean | Entrada discreta que inicia o tracking externo. |
| TRK_SCALE | Nenhuma | Os valores de escala superior e inferior, a unidade de engenharia e o número de dígitos à direita da vírgula decimal associados ao valor de rastreamento externo (TRK_VAL).|
| TRK_VAL | unidade de engenharia e limites de TRK_SCALE | Unidade de engenharia de TRK_SCALE
A entrada analógica usada na função de rastreamento externo. |

---

### Cálculo de Feedforward

Você pode ativar a função de feedforward por meio do parâmetro FF_ENABLE. Quando FF_ENABLE está definido como True, o valor de feedforward (FF_VAL) é escalonado (FF_SCALE) para uma faixa comum, garantindo compatibilidade com a escala de saída (OUT_SCALE). Um valor de ganho (FF_GAIN) é aplicado para atingir a contribuição total do feedforward.

### Rastreamento (Tracking)

Você pode especificar o rastreamento da saída por meio de opções e parâmetros de controle. As opções de controle podem ser definidas apenas no modo Fora de Serviço.

A opção de controle Track Enable (CONTROL_OPTS) deve estar como True para que a função de rastreamento opere. Quando a opção Track in Manual está como True, o rastreamento pode ser ativado e mantido quando o bloco estiver no modo Manual (Man). Quando Track in Manual está como False, o rastreamento é desabilitado no modo Manual.

A ativação da função de rastreamento faz com que o modo real do bloco passe para Local Override (LO).

O parâmetro de valor de rastreamento (TRK_VAL) especifica o valor a ser convertido e aplicado à saída quando o rastreamento estiver ativo. O parâmetro de escala de rastreamento (TRK_SCALE) define a faixa de TRK_VAL.

Quando o parâmetro de controle de rastreamento (TRK_IN_D) está como True e a opção Track Enable está habilitada, a entrada TRK_VAL é convertida para o valor apropriado e aplicada à saída em unidades de OUT_SCALE.

### Restrições de limites de Setpoint e Saída

Durante o download, os parâmetros OUT_HI_LIM, OUT_LO_LIM, SP_HI_LIM e SP_LO_LIM são definidos com seus valores configurados. Caso esses valores não tenham sido alterados dos padrões, eles são definidos da seguinte forma na primeira execução do bloco:

OUT_HI_LIM é definido como OUT_SCALE(EU100)
OUT_LO_LIM é definido como OUT_SCALE(EU0)
SP_HI_LIM é definido como PV_SCALE(EU100)
SP_LO_LIM é definido como PV_SCALE(EU0)

Durante a execução (runtime), os limites são restringidos da seguinte forma:

OUT_HI_LIM é limitado a:
OUT_SCALE(EU100) + 0,1 × (OUT_SCALE(EU100) - OUT_SCALE(EU0))
OUT_LO_LIM é limitado a:
OUT_SCALE(EU0) - 0,1 × (OUT_SCALE(EU100) - OUT_SCALE(EU0))
SP_HI_LIM é limitado a:
PV_SCALE(EU100) + 0,1 × (PV_SCALE(EU100) - PV_SCALE(EU0))
SP_LO_LIM é limitado a:
PV_SCALE(EU0) - 0,1 × (PV_SCALE(EU100) - PV_SCALE(EU0))

### Seleção e Limitação da Saída

A seleção da saída é determinada pelo modo de operação. Nos modos **Auto, Cas e RCas**, a saída é calculada pela equação de controle PID. Nos modos **Man e ROut**, a saída pode ser inserida manualmente.

Você pode limitar a saída configurando os parâmetros **OUT_HI_LIM** e **OUT_LO_LIM**.

### Transferência sem impacto (Bumpless Transfer) e Rastreamento de Setpoint

Deverá ser possível habilitar o rastreamento de setpoint configurando as seguintes opções de controle 

(**CONTROL_OPTS**):
* **SP-PV Track in LO or IMan**
* **SP-PV Track in Man**
* **SP-PV Track in ROut**

Quando uma dessas opções está habilitada, o valor de **SP** passa a acompanhar o valor de **PV** no modo especificado.

Apenas deve ser possível configurar as opções de controle apenas no modo **Fora de Serviço**.

Os parâmetros SP ou OUT não são alterados como resultado de mudanças na escala ou nos limites. No entanto, se OUT violar os novos limites, ele será forçado para dentro desses limites na próxima execução do algoritmo.

### IO_OPTS

Grupo de parâmetros chamado IO_OPTS, permite selecionar como os sinais de entrada e saída são processados. Você pode definir as opções de I/O (input/output) apenas nos modos MANUAL (MAN) ou Fora de Serviço (OOS). A seguir estão as opções de I/O:

**Low Cutoff** — Quando o valor de entrada convertido está abaixo do limite especificado pelo parâmetro LOW_CUT e o Low Cutoff está habilitado (True), um valor de 0,0 é usado como valor convertido (PV). Esta opção pode ser útil com dispositivos de medição baseados em zero, como medidores de vazão.

**Target to Man if Fault State activated** — Define o MODE.TARGET como Manual (Man), perdendo o MODE.TARGET original, caso o estado de falha seja ativado. 

**Fault State to value** — Ação de saída a ser tomada quando ocorre falha. (0: congelar, 1: ir para valor pré-definido)

**Increase to Close** — Indica se o valor de saída CO calculado pelo algoritmo deve ser invertido antes de ser escrito efetivamente na variável de saída no servidor OPC-UA.

**SP-PV Track in LO or IMan** — Permite que o SP acompanhe a PV quando o modo real do bloco é LO (Local Override - quando o tracking está ativo). SP-PV Track in Man tem precedência sobre esta opção. SP-PV Track in Man deve estar habilitado para que essa opção funcione quando o modo alvo for MAN.

**SP-PV Track in Man** — Permite que o SP acompanhe a PV quando o modo alvo do bloco é Manual (Man).

### Opções de Controle

O parâmetro de opções de controle (CONTROL_OPTS) permite selecionar opções de estratégia de controle. Você pode definir essas opções apenas nos modos Manual ou Fora de Serviço. A seguir estão as opções de controle:

**No OUT Limits in Manual** — Não aplica OUT_HI_LIM ou OUT_LO_LIM quando os modos alvo e real são Manual. Ainda assim, OUT será limitado a no máximo 10% fora da faixa de OUT_SCALE.

**Obey SP Limits if Cas or RCas** — Normalmente, um setpoint em cascata não é restrito pelos limites de setpoint do bloco a jusante, exceto quando inserido manualmente. Se esta opção estiver ativa, o setpoint em cascata será limitado pelos limites absolutos nos modos Cas e RCas. Se o limite do SP do bloco a jusante for atingido, a ação integral é suspensa caso este o algoritmo esteja funcionando como MESTRE de outro controlador PID.

**Track in Manual** — Permite a função de tracking externo quando o modo alvo é MAN, desde que Track Enable esteja habilitado. Caso contrário, o tracking externo não é permitido no modo MAN.

**Track Enable** — Habilita a função de tracking externo. Quando TRK_IN_D for verdadeiro e o modo alvo não for MAN (ou Track in Manual estiver ativo), o bloco entra em LO (Local Override) e a saída assume o valor de TRK_VAL.

**Direct Acting** — Define a relação entre PV e saída. Quando habilitado, um aumento na PV resulta em aumento na saída. Importante parâmetro ao configurar um PID.

**SP Track Retained Target** — Permite que o SP acompanhe o parâmetro RCas ou Cas com base no modo alvo retido, quando o MODE.ACTUAL LO, Man ou ROut. Esta opção tem precedência sobre outras opções de tracking SP-PV.

**SP-PV Track in LO or IMan** — Permite que o SP acompanhe a PV nos modos LO. Depende da habilitação de SP-PV Track in Man quando o modo alvo for MAN.

**SP-PV Track in ROut** — Permite que o SP acompanhe a PV quando o modo real for ROut.

**SP-PV Track in Man** — Permite que o SP acompanhe a PV quando o modo alvo for Manual.

### Alarmes configuráveis

A detecção de alarmes do bloco é baseada nos valores de **PV** e **SP**. Você pode configurar os seguintes limites de alarme para comparação com o valor de PV na detecção de alarmes:

* **Alto (HI_LIM)**
* **Alto-alto (HI_HI_LIM)**
* **Baixo (LO_LIM)**
* **Baixo-baixo (LO_LO_LIM)**

Você pode configurar os seguintes limites de alarme para comparação com a diferença entre os valores de SP e PV (erro de processo) na detecção de alarmes de desvio:

* **Desvio alto (DV_HI_LIM)**
* **Desvio baixo (DV_LO_LIM)**

**Nota**
Os alarmes de desvio são suprimidos durante alterações no SP.

### Tratamento de status do bloco de função PID

O MODE.ACTUAL do PID passa para **Manual (Man)** quando o status da **PV** é **Ruim (Bad)**. Por meio do parâmetro **STATUS_OPTS**, você pode determinar quais condições farão com que o status da PV seja considerado **Bad**.

O processamento do status de entrada dentro do algoritmo do PID para determinar o status da PV pode ser modificado pelas opções de status (**STATUS_OPTS**). As opções são:

* **Bad if Limited** (Ruim se limitado)
* **Uncertain if Limited** (Incerto se limitado)
* **Target to Manual if Bad IN** (Mudar para Manual se IN estiver ruim)
* **Use Uncertain as Good** (Usar Incerto como Bom)


### **3.3. Temporização e Segurança (Fail-Safes)**
* **Determinismo:** Scan rates configuráveis por malha (100ms, 500ms, 1s, 2s, 5s, 10s, 30s, 60s).
* **Anti-Windup:** Pausa o acúmulo integral se a CO atingir limites (0% ou 100%).
* **Bumpless Transfer:** Ao ativar ajuste inteligente ou ir para AUTO, o termo integral é recalculado instantaneamente.
* **Watchdog Heartbeat:** Gerar sinal pulsante para PLC. Se o App cair, ou travar, o PLC tem condisções de detectar e assumir valores de segurança. Além do sinal wpulsante, crie duas variáveis chamdadas WD_HEART_BEAT, WD_HEART_BEAT_NOT. Na inicialização do sistema atribua TRUE para WD_HEART_BEAT e o valor desta variável de deverá passar por uma lógica NOT a cada SCAN do algoritmo e o resultado escrito em WD_HEART_BEAT_NOT. A ideia é que no PLC o usuário leia o valor WD_HEART_BEAT_NOT e escreva de volta em WD_HEART_BEAT, isso vai gerar um valor pulsante dentro do PLC que também poderá ser verificado pelo sistema externo conectado para perceber que o algoritmo do PID parou de executar.
