# Hive reader

This script was thrown together for me to be able to gather metrics and perform checks on my Hive Home installation.

I am quite aware that it could have it's commands refactored nicely to handle what arguments are required for each
command, etc.

It also has a reasonably large dependency - `pyhiveapi`.
I'm sure I could have got the API working using smaller dependencies like `requests`, but to be honest, I just wanted to
get something up and running so I could start monitoring my home.

I use it for [Sensu Go](https://sensu.io/), but it could work for various other monitoring methods.
When I gather metrics, I'm currently storing them in [Graphite Go](https://github.com/go-graphite), so the metrics only
support the Graphite format, though I expect it would be reasonably straight forward to use another format.

# Usage

All commands can be used with the `--session-file FILENAME` option - a file that the session, tokens, etc will be saved to.
Using this session file means that each run of the script doesn't require a login (and the associated 2FA input).

If this option is omitted, the session will be saved to `~/hive-session.json`.

The `save`, `metrics`, and `battery` commands will not work until you have successfully authenticated with the `login` command.

## Login

Before you can start using the API, you will need to authenticate.
This is done with

```
./hivereader.py login --username USERNAME --password PASSWORD
```

When using the login command, the username and password options are required.

This command handles the two factor authentication via SMS feature, so you'll be asked for the code sent to you by Hive.

## Save

This is only really for debugging as I was digging into the data available from Hive.
I thought I may as well allow it to dump the returned data for later debugging or if I buy a new class of device and
want to revisit the data returned in future.

The save command has an optional argument `--save-file FILENAME`, which is the file that the Hive data will be saved to.
It defaults to `data.json`.

```
./hivereader.py save --save-file hivedata.json
```

## Metrics

The metrics output is the Graphite format.
It ought to be straight forward to support other formats in the future, but I use Graphite Go at the moment.

```
./hivereader.py metrics
```

This currently returns metrics for devices where available:

- **temperature:** the current temperature as recorded by the device)
- **target:** the temperature that the device is set to (such as the current scheduled temperature for the thermostat or
  thermostatic radiator valve)
- **boost:** if the device is boosted (I'm not confident that this works as I think it works at the moment)
- **battery:** if the device has a battery, the percentage charge is returned

## Battery

The battery command is a check of battery charge.
The warning and critical threshold can be configured with `--warning WARNING_THRESHOLD` and `--critical CRITICAL_THRESHOLD`.

The default warning threshold is 20, and the default critical threshold is 5.
I've not looked to see what percentage triggers a device to show the low battery icon.

If a single battery charge percentage is lower than the critical threshold, the check will result in a critical status.
If a single battery's charge is lower than the warning threshold, the check will result in a warning status.
Otherwise an OK status is returned.

In all cases, the check output lists battery levels for batteries at critical or warning values.

```
./hivereader.py battery
```
