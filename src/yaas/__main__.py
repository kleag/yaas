"""yaas.__main__: executed when yaas directory is called as a script."""


from .app import main

# Guarded: the separation's child processes (see local_extraction.py)
# re-import the main module, and must not start another app.
if __name__ == "__main__":
    main()
