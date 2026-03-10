import streamlit as st
import pandas as pd
import os
import matplotlib.cm as cm
import matplotlib.colors as mcolors

st.set_page_config(page_title="Hourly DC Dashboard", layout="wide")

st.title("Hourly Productivity Dashboard")

SAVE_FOLDER="saved_hourly_files"
os.makedirs(SAVE_FOLDER,exist_ok=True)

selected_date=st.date_input("Select Date")
date_str=selected_date.strftime("%d/%m/%Y")

slots=["09","10","11","12","13","14","15","16","17"]

slot_labels={
"09":"09.00 AM",
"10":"10.00 AM",
"11":"11.00 AM",
"12":"12.00 PM",
"13":"01.00 PM",
"14":"02.00 PM",
"15":"03.00 PM",
"16":"04.00 PM",
"17":"05.00 PM"
}

INTERNET_USERS=["SL1062","SL268","SL1228","SL1403","SL1217"]
EFEED_USERS=["SL1525","SL456","SL487","SL1053","SL1520"]

# ---------------- USER MASTER ----------------

st.sidebar.header("User Master")

user_file=st.sidebar.file_uploader("Upload User List",type=["xlsx"])

user_map={}

if user_file:
    users=pd.read_excel(user_file)
    user_map=dict(zip(users["UID"],users["Name"]))

# ---------------- HOURLY FILES ----------------

st.sidebar.header("Hourly Files")

uploaded_files={}

for slot in slots:

    col1,col2=st.sidebar.columns([3,1])

    file=col1.file_uploader(slot_labels[slot],type=["xlsx"],key=slot)

    delete_clicked=col2.button("❌",key=f"del{slot}")

    path=os.path.join(SAVE_FOLDER,f"{slot}.xlsx")

    if delete_clicked:
        if os.path.exists(path):
            os.remove(path)
        st.rerun()

    if file:
        with open(path,"wb") as f:
            f.write(file.getbuffer())

        uploaded_files[slot]=path

for slot in slots:

    path=os.path.join(SAVE_FOLDER,f"{slot}.xlsx")

    if os.path.exists(path) and slot not in uploaded_files:
        uploaded_files[slot]=path

# ---------------- DATA EXTRACTION ----------------

def extract_counts(df,column):

    completed={}
    onhold={}

    for val in df[column].dropna():

        if "/" not in str(val):
            continue

        status,uid=val.split("/")

        status=status.strip()
        uid=uid.strip()

        if uid.startswith("F"):
            continue

        if status=="Completed":
            completed[uid]=completed.get(uid,0)+1

        if status=="On hold":
            onhold[uid]=onhold.get(uid,0)+1

    return completed,onhold


def extract_qc_completed(df):

    qc_completed={}

    if "QC" not in df.columns:
        return qc_completed

    for val in df["QC"].dropna():

        if "/" not in str(val):
            continue

        status,uid=val.split("/")

        status=status.strip()
        uid=uid.strip()

        if uid.startswith("F"):
            continue

        if status=="Completed":
            qc_completed[uid]=qc_completed.get(uid,0)+1

    return qc_completed


def latest_completed_counts(df,column):

    counts={}

    for val in df[column].dropna():

        if "/" not in str(val):
            continue

        status,uid=val.split("/")

        status=status.strip()
        uid=uid.strip()

        if uid.startswith("F"):
            continue

        if status=="Completed":
            counts[uid]=counts.get(uid,0)+1

    return counts

# ---------------- BUILD TABLE ----------------

def build_table(data,latest_dc,fixed_users=None,include_total=True):

    users=set()

    if fixed_users:
        users.update(fixed_users)

    for slot in data:
        users.update(data[slot].keys())

    rows=[]

    for uid in users:

        row={}
        row["Name"]=user_map.get(uid,"")
        row["UID"]=uid

        for slot in slots:
            row[slot_labels[slot]]=data.get(slot,{}).get(uid,0)

        if include_total:
            row["Total DC"]=latest_dc.get(uid,0)

        rows.append(row)

    df=pd.DataFrame(rows)

    if df.empty:
        return df

    columns=["Name","UID"]+[slot_labels[s] for s in slots]

    if include_total:
        columns.append("Total DC")

    df=df[columns]

    totals=df.iloc[:,2:].sum()

    total_row={"Name":"Count","UID":""}

    for col in totals.index:
        total_row[col]=totals[col]

    df=pd.concat([df,pd.DataFrame([total_row])],ignore_index=True)

    return df

# ---------------- COLOR ENGINE ----------------

def lighten_color(rgb,amount=0.5):

    r,g,b=rgb
    r=int(r+(255-r)*amount)
    g=int(g+(255-g)*amount)
    b=int(b+(255-b)*amount)

    return r,g,b

from matplotlib import colormaps

def apply_gradient(df,reverse=False):

    if df.empty:
        return df.style
    
    styled=df.style.set_properties(**{
        "font-weight":"bold",
        "text-align":"center",
        "border":"1px solid black"
    })

    styled=styled.set_table_styles([
        {"selector":"th","props":[
          ("font-weight","bold"),
          ("color","black"),
          ("background-color","#d0d0d0"),
          ("border","1px solid black") 
        ]},
        {"selector":"td","props":[
            ("border","1px solid black")
        ]}
    ])

    last=len(df)-1
    rows=list(range(last))

    if last<0:
        return styled
    
    cmap=colormaps.get_cmap("RdYlGn")

    for col in df.columns[2:]:
        values=df.loc[rows,col]

        if values.sum()==0:

            styled=styled.map(
                lambda x:"background-color:#f2f2f2",
                subset=(rows,[col])
            )
            continue

        norm=mcolors.Normalize(vmin=values.min(),vmax=values.max())

        def color (val) :

            if reverse:
                c=cmap(1-norm(val))
            else:
                c=cmap(norm(val))

            r=int(c[0]*255)
            g=int(c[1]*255)
            b=int(c[2]*255)

            r,g,b=lighten_color((r,g,b),0.5)

            return f"background-color:rgb({r},{g},{b})"
        
        styled=styled.map(color,subset=(rows,[col]))

    styled=styled.map(
        lambda x:"background-color:#e6f2ff",
        subset=([last],df.columns)
    )

    return styled

# ---------------- PROCESS DATA ----------------

internet_completed={}
internet_onhold={}

efeed_completed={}
efeed_onhold={}

qc_completed={}

latest_file_df=None

for slot,path in uploaded_files.items():

    df=pd.read_excel(path)

    latest_file_df=df

    filtered=df[
        (df["is_duplicate"].isna()) &
        (df["is_processable"]=="VALID")
    ]

    ic,io=extract_counts(filtered,"Internet Data Capturing")
    internet_completed[slot]=ic

    raw_ic,raw_io=extract_counts(df,"Internet Data Capturing")
    internet_onhold[slot]=raw_io

    ec,eo=extract_counts(filtered,"EFeed Data Capturing")
    efeed_completed[slot]=ec

    raw_ec,raw_eo=extract_counts(df,"EFeed Data Capturing")
    efeed_onhold[slot]=raw_eo

    qc_completed[slot]=extract_qc_completed(df)

latest_dc_internet={}
latest_dc_efeed={}

if latest_file_df is not None:

    latest_dc_internet=latest_completed_counts(latest_file_df,"Internet Data Capturing")
    latest_dc_efeed=latest_completed_counts(latest_file_df,"EFeed Data Capturing")

# ---------------- DASHBOARD ----------------

tab1,tab2,tab3=st.tabs(["Internet","Efeed","QC"])

with tab1:

    st.subheader(f"Completed - {date_str}")

    table=build_table(internet_completed,latest_dc_internet,INTERNET_USERS,True)

    st.markdown(apply_gradient(table,False).to_html(),unsafe_allow_html=True)

    st.subheader(f"Onhold - {date_str}")

    table2=build_table(internet_onhold,{},INTERNET_USERS,False)

    st.markdown(apply_gradient(table2,True).to_html(),unsafe_allow_html=True)

with tab2:

    st.subheader(f"Completed - {date_str}")

    table3=build_table(efeed_completed,latest_dc_efeed,EFEED_USERS,True)

    st.markdown(apply_gradient(table3,False).to_html(),unsafe_allow_html=True)

    st.subheader(f"Onhold - {date_str}")

    table4=build_table(efeed_onhold,{},EFEED_USERS,False)

    st.markdown(apply_gradient(table4,True).to_html(),unsafe_allow_html=True)

with tab3:

    st.subheader(f"QC Completed - {date_str}")

    table_qc=build_table(qc_completed,{},None,False)

    st.markdown(apply_gradient(table_qc,False).to_html(),unsafe_allow_html=True)