
from ib_insync import *
ib = IB()
ib.connect("127.0.0.1", 4002, clientId=50)

#contract = Future("MNQ", "202512", "CME")   # is working
contract = Future("MNQ", "202503", "CME")   # is not working
bars = ib.reqHistoricalData(
    contract,
    endDateTime="",
    durationStr="1 D",
    barSizeSetting="1 min",
    whatToShow="TRADES",
    useRTH=True

)
print(bars)