' Wrapper: run the digest batch completely hidden so no console window
' appears on the desktop (an accidentally-closed window kills the run
' with STATUS_CONTROL_C_EXIT). Invoked by Task Scheduler instead of the
' .cmd directly. Output still goes to state\_run.log via the batch file.
CreateObject("WScript.Shell").Run """D:\Project\dailynews\routine\run-local-digest.cmd""", 0, False
