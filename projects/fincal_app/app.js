let chart
let portfolioChart

function preset(m,r,y){
document.getElementById("monthly").value=m
document.getElementById("rate").value=r
document.getElementById("years").value=y
}

function calculateSIP(){

const monthly=parseFloat(document.getElementById("monthly").value)
const rate=parseFloat(document.getElementById("rate").value)/100/12
const years=parseInt(document.getElementById("years").value)
const goal=parseFloat(document.getElementById("goal").value)

if(!monthly||!rate||!years){
alert("Enter values")
return
}

let months=years*12
let balance=0

let data=[]
let labels=[]

for(let i=1;i<=months;i++){

balance=balance*(1+rate)+monthly

if(i%12===0){
labels.push("Year "+(i/12))
data.push(Math.round(balance))
}

}

let invested=monthly*months
let returns=balance-invested

updateNumbers(invested,returns,balance)

drawChart(labels,data)

updateGoal(goal,balance)

healthScore(monthly,years)

portfolio()

}

function drawChart(labels,data){

const ctx=document.getElementById("chart")

if(chart)chart.destroy()

chart=new Chart(ctx,{
type:"line",
data:{
labels:labels,
datasets:[{
label:"Investment Growth",
data:data,
borderWidth:3,
tension:0.3
}]
},
options:{
animation:{duration:1500},
plugins:{legend:{labels:{color:"white"}}},
scales:{
x:{ticks:{color:"#94a3b8"}},
y:{ticks:{color:"#94a3b8"}}
}
}
})

}

function updateNumbers(inv,ret,fv){

document.getElementById("invested").innerText="₹"+inv.toLocaleString()
document.getElementById("returns").innerText="₹"+Math.round(ret).toLocaleString()
document.getElementById("future").innerText="₹"+Math.round(fv).toLocaleString()

}

function updateGoal(goal,fv){

if(!goal)return

let percent=Math.min((fv/goal)*100,100)

document.getElementById("goalProgress").style.width=percent+"%"

document.getElementById("goalText").innerText=
percent.toFixed(1)+"% of goal achieved"

}

function healthScore(monthly,years){

let score=Math.min(100,(monthly/5000)*40+(years/20)*60)

document.getElementById("healthScore").innerText=
Math.round(score)

}

function portfolio(){

const ctx=document.getElementById("portfolioChart")

if(portfolioChart)portfolioChart.destroy()

portfolioChart=new Chart(ctx,{
type:"pie",
data:{
labels:["Equity","Debt","Gold"],
datasets:[{
data:[60,25,15]
}]
}
})

}

function askAI(){

const q=document.getElementById("aiQuestion").value.toLowerCase()
const out=document.getElementById("aiAnswer")

if(q.includes("sip"))
out.innerText="SIP means investing a fixed amount regularly to reduce market risk."

else if(q.includes("mutual"))
out.innerText="Mutual funds pool money from investors to invest in stocks and bonds."

else if(q.includes("risk"))
out.innerText="Higher returns often come with higher risk. Diversification helps manage risk."

else if(q.includes("compound"))
out.innerText="Compounding means earning returns on both your investment and previous gains."

else
out.innerText="Invest regularly and stay invested long term for better wealth creation."

}