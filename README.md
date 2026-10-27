    # SigmaOS-libappindicator

    Sys-tray appindicator library

    Part of the **SigmaOS** sovereign operating-system ecosystem — a multi-repository
    distribution modelled on Linux Mint and Omarchy Linux. See the parent
    [`SigmaOS`](https://github.com/AaryanSinghChauhan09/SigmaOS) repository for the
    full component index.

    ## Upstream inspirations
    - https://github.com/linuxmint/libappindicator

    ## Design principles applied
    - **Abstraction**
- **Single Source of Truth**
- **Fail-Fast**
- **Defensive Programming**
- **KISS**
- **DRY**
- **Deterministic Testing**

    ## Usage
    Verbs: `widgets, icon, thumbnailers, bindings-plan`

    ```
    $ sigma-xapp widgets inventory.txt
core         3   deprecated   1   unavailable  1
$ sigma-xapp icon folder-open --theme-dir ~/.icons/Mint-Y/scalable
~/.icons/Mint-Y/scalable/apps/folder-open.svg
$ sigma-xapp thumbnailers ./thumbnailers
sigma-png.thumbnailer   ok (2 mime types)
$ sigma-xapp bindings-plan Gtk.Button Xapp.StatusIcon GdkPixbuf.Pixbuf
import gi
gi.require_version("Gtk", "3.0")

    ```

    ## Build & test
    ```
    make build
    make test
    ```

    ## Licence
    GNU General Public License v3.0 (FOSS).
