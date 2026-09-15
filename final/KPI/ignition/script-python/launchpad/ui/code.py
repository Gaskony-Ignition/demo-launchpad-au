"""Appearance: the themes this gateway can offer, for the Settings page.

Byte-identical in OEE and in KPI, for the same reason launchpad.setup is: two
copies of one list drift, and the half that drifts is the half nobody reads.
"""


def themeOptions():
    """Options for the Settings page's theme dropdown.

    Ignition's stock six first, in their usual order, then every custom theme
    the gateway carries as a config resource under
    com.inductiveautomation.perspective/themes -- labelled from its own name,
    so 'nord-dark' reads as 'Nord dark'.

    The stock six are a fixed base rather than something read from the listing:
    `light` and `dark` live inside the Perspective module's own jar and never
    appear as resources at all, while the four variants do, so reading the
    listing alone would offer four of the six. Anything the listing repeats is
    dropped rather than shown twice.

    If the listing fails the dropdown still offers the stock six, which are the
    ones guaranteed to be on any gateway -- an appearance control is not worth
    an error banner on a page whose real job is the Setup button.
    """
    from java.lang import Throwable as JThrowable
    stock = [u"light", u"light-warm", u"light-cool",
             u"dark", u"dark-warm", u"dark-cool"]
    extra = []
    try:
        for res in system.config.getResources(
                moduleId="com.inductiveautomation.perspective", typeId="themes"):
            name = unicode(res.getName())
            if name not in stock and name not in extra:
                extra.append(name)
    except (JThrowable, Exception) as exc:
        # java.lang.Throwable as well as Exception: a Jython `except Exception`
        # does not catch a Java Error, and system.config raises through the JVM.
        system.util.getLogger("launchpad.ui").warn(u"theme listing failed: %s" % exc)
    return [{u"value": n, u"label": n.replace(u"-", u" ").capitalize()}
            for n in stock + sorted(extra)]
