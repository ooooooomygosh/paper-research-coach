---
title: The TCP three-way handshake
---
Short answer: both sides confirm they can send and receive before they send data.

## Messages
```sequence num
Client -> Server: SYN, seq=x
Server -> Client: SYN+ACK, seq=y, ack=x+1
Client -> Server: ACK, ack=y+1
note Client, Server: ESTABLISHED
== data starts ==
Client --> Server: first request
```

## States
```flow LR
(CLOSED) -> LISTEN: passive open
LISTEN -> SYN_RCVD: get SYN
SYN_RCVD -> *ESTABLISHED: get ACK
```

## Parts
```tree
Handshake | three messages
  SYN | client asks to connect
  *SYN+ACK | server agrees and asks back
  ACK | client confirms
```

## History
```timeline
1974 | TCP is first described | Cerf and Kahn
*1981 | RFC 793 | the base standard
2022 | RFC 9293 | the current standard
```

## Facts
```kv cols=2
* Layer: transport
Reliable: yes
Port: any
```
