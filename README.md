# table-control

Generic 3-axis table control software.

## Supported Controllers

- ITK CorvusTT
- ITK Hydra

## SCPI Socket

The application can be used as generic proxy for different table controllers.
Make sure to enable and configure the SCPI socket in the application preferences.

|Command |Description |Example |
|--------|------------|--------|
|`*IDN?` | application identity | `*IDN?` -> `table-control v0.1.0` |
|`*CLS` | clears error stack | `*CLS` |
|`[:]POSition?` | get position | `POS?` -> `0.000 0.000 0.000` |
|`[:]CALibration[:STATe]?` | get calibration | `CAL?` -> `3 3 3` (`1`=cal, `2`=rm, `3`=cal+rm) |
|`[:]MOVE[:STATe]?` | is moving? | `MOVE?` -> `1` |
|`[:]MOVE:RELative <POS>` | 3-axis relative move | `MOVE:REL 0 0 4.200` |
|`[:]MOVE:ABSolute <POS>` | 3-axis absolute move | `MOVE:ABS 10.000 20.000 2.000` |
|`[:]MOVE:ABORT` | abort a movement | `MOVE:ABORT` |
|`[:]SYStem:ERRor[:NEXT]?` | next error on stack | `SYS:ERR?` -> `0,"no error"` |
|`[:]SYStem:ERRor:COUNt?` | size of error stack | `SYS:ERR:COUN?` -> `0` |

All SCPI commands are case insensitive (e.g. `pos?` is equal to `POS?`).

## Legacy TCP Socket

The application can emulate a legacy TCP commands used with LabView.
Make sure to enable and configure the TCP socket in the application preferences.

|Command |Description |Example |
|--------|------------|--------|
|`PO?` | get position and status | `PO?` -> `0.000000,0.000000,0.000000,0` |
|`MR=<DELTA>,<AXIS>` | 1-axis relative move (x=1, y=2, z=3) | `MR=4.200,1` |
|`MA=<X>,<Y>,<Z>` | 3-axis absolute move | `MA=10.000,20.000,2.000` |
|`???` | prints help | |

All legacy TCP commands are case sensitive.

## Download

See for pre-built Windows binaries in the [releases](https://github.com/hephy-dd/table-control/releases) section.

## License

table-control is licensed under the [GNU General Public License Version 3](https://github.com/hephy-dd/table-control/tree/main/LICENSE).
