import pandas as pd
import streamlit as st

exchange_rate = 1350 # 적용환율

df = pd.read_csv("./data/real_account_test2.csv") # 데이터 로드

# 데이터 가공
df['1주당_취득가액'] = round(df['매입원가'] / df['보유수량'])
df['1주당_매도가격'] = round(df['평가금액'] / df['보유수량'])
df['1주당_손실액_환율'] = df['1주당_매도가격'] - df['1주당_취득가액']
df['손실율'] = round((df['1주당_매도가격'] - df['1주당_취득가액'])*100/df['1주당_취득가액'],2)
df['손실금액'] = df['1주당_손실액_환율'] * df['보유수량'] # 종목당 손실금액
df['매도금액'] = df['평가금액'] # 종목당 매도금액
df['체결손실액'] = df['체결금액'] - df['1주당_취득가액']*df['체결수량']
df['총보유수량'] = df['보유수량'] - df['체결수량']
df.rename(columns={'티커' : '종목코드'}, inplace=True)

def show_concluded_stock(df, accounting_number) :
    df1 = df[(df['계좌번호'] == accounting_number) & (df['체결수량']!=0)].reset_index(drop=True)
    return df1

def find_loss_stock_buffer(df):
    # 총 보유수량이 0인 종목은 제외하여 추천
    # 종목 당 손실금액 : 손실금액의 절대값이 클 수록 (buffer1)
    # 종목 당 손실률 : 손실률의 절대값이 클수록 (buffer2)
    # 종목 당 매도금액 : 매도금액이 작을수록 (buffer3)
    # 종목의 1주 당 가격 : 매도금액이 작을수록 (buffer4)
    df1 = df[df['총보유수량']!=0]

    buffer1 = df1['손실금액'].min() * (-0.05) # 손실금액 버퍼 구하기
    df_loss = df1[(df1['손실금액'] >= df1['손실금액'].min() - buffer1) & (df1['손실금액'] <= df1['손실금액'].min() + buffer1)]

    if df_loss.shape[0] == 1:
        return df_loss
    else:
        buffer2 = df_loss['손실율'].min() * (-0.05) # 손실율 버퍼 구하기
        df_loss = df_loss[
            (df_loss['손실율'] >= df_loss['손실율'].min() - buffer2) & (df_loss['손실율'] <= df_loss['손실율'].min() + buffer2)]
        if df_loss.shape[0] == 1:
            return df_loss
        else:
            buffer3 = df_loss['매도금액'].min() * (0.05) # 매도금액 버퍼 구하기
            df_loss = df_loss[(df_loss['매도금액'] >= df_loss['매도금액'].min() - buffer3) & (
                        df_loss['매도금액'] <= df_loss['매도금액'].min() + buffer3)]
            if df_loss.shape[0] == 1:
                return df_loss
            else:
                buffer4 = df_loss['1주당_매도가격'].min() * (0.05) # 매도가격 버퍼 구하기
                df_loss = df_loss[(df_loss['매도금액'] >= df_loss['매도금액'].min() - buffer3) & (
                            df_loss['1주당_매도가격'] <= df_loss['1주당_매도가격'].min() + buffer4)]
                if df_loss.shape[0] == 1:
                    return df_loss
                else:
                    return pd.DataFrame()
                    print("추천불가")

def tax_loss_harvesting(df, money, dict, accounting_number, buffer):
    df1 = df[df['계좌번호'] == accounting_number] # 계좌번호로 필터링
    conclude_loss_money = df1['체결손실액'].sum() # 기체결로 인해 이미 손실된 손실액 합계
    df_loss = find_loss_stock_buffer(df1)  # 알고리즘 기준을 만족하는 종목 선정

    if df_loss.shape[0] != 0 :

        loss_money = df_loss['1주당_손실액_환율'].values[0] * df_loss['총보유수량'].values[0] # 매도 기준에 선정된 종목의 1주당 손실액 * 총보유수량(기체결 수량 제외)

        result_money = money * (1-buffer) + conclude_loss_money + loss_money # 과세표준 * 버퍼 (%) + 기체결로 인한 손실액 + 위의 선정된 종목의 매도 손실액

        if result_money >= 0: # 결과가 양수라면 총 보유수량 그대로 넣으면 됨
            print(f"{df_loss['종목코드'].values[0]}를 {df_loss['총보유수량'].values[0]}주 만큼 파세요")
            print(f"손실 금액 : {loss_money}")
            print(f"남은 과세표준 : {result_money}")
            df_remain = df.drop(df_loss.index).reset_index(drop=True) # 추천 종료된 종목은 제외

            dict['종목코드'].append(df_loss['종목코드'].values[0])
            dict['매도주수'].append(df_loss['총보유수량'].values[0])
            dict['손실금액'].append(loss_money)

            if len(dict['종목코드']) == 3 : # 3종목으로 채워졌을 경우 추천 종료
                return pd.DataFrame(dict)

            # 2번째 기준에 부합하는 종목 선정
            tax_loss_harvesting(df_remain, result_money, dict, accounting_number, buffer = 0)

        else: # 결과가 음수라면 총보유수량을 하나씩 줄여가며 금액 확인 계산
            df_loss_quantity = df_loss['총보유수량'].values[0]
            while (df_loss['1주당_손실액_환율'].values[0] * df_loss_quantity) + money * (1-buffer) + conclude_loss_money< 0:
                df_loss_quantity = df_loss_quantity - 1
                if (df_loss['1주당_손실액_환율'].values[0] * df_loss_quantity) + money * (1-buffer) + conclude_loss_money >= 0:
                    if df_loss_quantity == 0 : # 주수가 0주라면 넣을 종목이 없는 것이므로 다음 기준에 해당하는 종목 선정 뒤 break
                        df_remain = df.drop(df_loss.index).reset_index(drop=True)
                        tax_loss_harvesting(df_remain, money, dict, accounting_number, buffer)
                        break

                    print(f"{df_loss['종목코드'].values[0]}를 {df_loss_quantity}주 만큼 파세요")
                    print(f"손실 금액 : {df_loss['1주당_손실액_환율'].values[0] * df_loss_quantity}")
                    print(f"남은 과세표준 : {df_loss['1주당_손실액_환율'].values[0] * df_loss_quantity + money * (1-buffer)}")

                    dict['종목코드'].append(df_loss['종목코드'].values[0])
                    dict['매도주수'].append(df_loss_quantity)
                    dict['손실금액'].append(df_loss['1주당_손실액_환율'].values[0] * df_loss_quantity)

                    if df_loss_quantity < df_loss['총보유수량'].values[0]: # 더 손실 시켜야하는 금액이 남은 상태에서 다음 종목으로 그 손실을 시킬 수 있는 경우
                        df_remain = df.drop(df_loss.index).reset_index(drop=True)
                        tax_loss_harvesting(df_remain, df_loss['1주당_손실액_환율'].values[0] * df_loss_quantity + money * (1-buffer), dict, accounting_number, buffer=0)
                        break

                    break

                elif len(dict['종목코드']) == 3: # 종목수 3종목으로 제한
                    break

                elif df_loss_quantity <= 0 : # 음수 방지
                    break
        return pd.DataFrame(dict)
    else :
        return pd.DataFrame({'종목코드' : [], '매도주수' : [], '손실금액' : []})
        print("손실 종목이 없습니다.")

if __name__ == "__main__" :
    dic = {'종목코드' : [], '매도주수' : [], '손실금액' : []}

    st.set_page_config(layout = 'wide')
    st.title("매도주수 추천기")

    accounting_select_box = st.selectbox("계좌번호", (list(df['계좌번호'].unique())))
    money = st.text_input("손실 시켜야하는 금액을 입력하세요.", value = 1500000)
    exchange_rate_buffer = st.slider("환율을 고려한 버퍼(%)를 선택하세요.", 0.0, 1.0, 0.1)
    scs = show_concluded_stock(df, accounting_select_box)
    TLH_result = tax_loss_harvesting(df, int(money), dict=dic, accounting_number=accounting_select_box,
                                     buffer=exchange_rate_buffer)

    col3, col4 = st.columns(2)
    with col3:
        container = st.container(border=True)
        container.write("<매도 시 발생 손실 금액 예상>")
        container.write(f"기체결 손실 금액 : {format(int(scs['체결손실액'].sum()), ',')}원")
        container.write(f"시뮬레이션 손실 금액 : {format(int(TLH_result['손실금액'].sum()), ',')}원")
        container.write(f"합계 : {format(int(scs['체결손실액'].sum()) + int(TLH_result['손실금액'].sum()), ',')}원")
        container.write("--------------------------------")
        container.write("<양도소득세>")
        container.write(f":red[절세 전 해외주식 양도소득세 : {format(round(int(money) * 0.22), ',')}원]")
        money2 = round(int(money) * 0.22) if int(money) < round(int(-(scs['체결손실액'].sum() + TLH_result['손실금액'].sum()))) else round(int(-(scs['체결손실액'].sum() + TLH_result['손실금액'].sum()) * 0.22))
        print(round(int(-(scs['체결손실액'].sum() + TLH_result['손실금액'].sum()) * 0.22)) )
        container.write(f"줄일 수 있는 양도소득세 : {format(money2, ',')}원")
        container.write(f"절세 후 양도소득세 : {format(round(int(money) * 0.22) - money2, ',')}원")



    with col4:
        st.write(f"과세표준 : {format(int(money), ',')}원")
        st.write(f":green[버퍼(%) : {exchange_rate_buffer}]")
        st.write(f"버퍼(%) 적용 후 과세표준 : {format(int(float(money)*(1-exchange_rate_buffer)), ',')}원")
        # st.write(f":red[절세 전 해외주식 양도세 : {format(round(int(money) * 0.22), ',')}원]")
        # st.write(f"절세 후 과세표준 : {format(int(money) + int(TLH_result['손실금액'].sum()), ',')}원")
        # st.write(f":red[절세 후 해외주식 양도세 : {format(round((int(money) + TLH_result['손실금액'].sum()) * 0.22), ',')}원]")

    col1, col2 = st.columns(2)

    with col1 :
        st.write("<손실 종목 리스트>")
        st.write(df[df['계좌번호']==accounting_select_box].reset_index(drop=True))
        st.write("<기체결 종목 리스트>")
        st.write(scs[['계좌번호', '종목코드', '보유수량', '체결수량', '총보유수량', '체결손실액']])
    with col2 :
        st.write('<매도 추천 종목 리스트>')
        st.write(TLH_result)