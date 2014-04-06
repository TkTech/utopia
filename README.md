# Utopia

Utopia aims to be a simple IRC framework. It is developed to meet the
needs of [Notifico][], a cia.vc replacement.

## Testing

Running the tests requires a local install of [ngircd][], which is a very
simple IRC daemon. The test setup and teardown will take care of launching
and shutting down ngircd.

The tests are compatible with [sniffer][], which will run the tests as files
are changed. Just run `sniffer` from the root of the project.


[Notifico]: http://github.com/TkTech/Notifico
[ngircd]: http://ngircd.barton.de/
[sniffer]: https://github.com/jeffh/sniffer/
