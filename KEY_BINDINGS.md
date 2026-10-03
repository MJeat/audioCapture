# GUI Keyboard Shortcuts

The keyboard shortcuts are configurable in the **Shortcuts** section of the GUI.

## Default keys

| Action | Default key |
|---|---|
| Record | `1` |
| Pause / Resume | `2` |
| Stop | `3` |

Click anywhere in the GUI outside a text input to leave the input cursor. The shortcut action is global within the GUI window. Click the GUI first if another application has focus.

## Changing a shortcut

1. Start [audio_capture_gui.py](./audio_capture_gui.py).
2. Find the **Shortcuts** row.
3. Click the input below **Record**, **Pause**, or **Stop**.
4. Replace the key with one single key character, such as:

   ```text
   r
   p
   s
   ```

5. Click anywhere in the GUI outside the shortcut input fields to leave the input.
6. The button labels update to show the new keys.

The new shortcuts take effect immediately. Avoid assigning the same key to multiple actions because one key would trigger multiple actions.

## Leaving a text input

Click anywhere in the GUI that is not a text input. The focus handler deliberately leaves text entries and dropdowns alone, so dropdown menus continue to open normally.

## Notes

- Use one key character for each action.
- If a key does not work, click the GUI window first so it has keyboard focus.
