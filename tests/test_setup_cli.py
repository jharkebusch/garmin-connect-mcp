import json

from garmin_mcp import setup_cli


class TestWriteConfig:
    def test_creates_the_file_when_none_exists(self, tmp_path):
        target = tmp_path / "Claude" / "claude_desktop_config.json"
        backup, replaced = setup_cli.write_config(target)
        assert backup is None
        assert replaced is False
        config = json.loads(target.read_text())
        assert config["mcpServers"]["garmin"]["args"] == ["-m", "garmin_mcp"]

    def test_keeps_other_mcp_servers_untouched(self, tmp_path):
        # Clobbering someone's existing servers would be the worst thing
        # this installer could do.
        target = tmp_path / "claude_desktop_config.json"
        target.write_text(
            json.dumps({"mcpServers": {"filesystem": {"command": "npx", "args": ["fs"]}}})
        )
        setup_cli.write_config(target)
        config = json.loads(target.read_text())
        assert config["mcpServers"]["filesystem"] == {"command": "npx", "args": ["fs"]}
        assert "garmin" in config["mcpServers"]

    def test_keeps_unrelated_top_level_settings(self, tmp_path):
        target = tmp_path / "claude_desktop_config.json"
        target.write_text(json.dumps({"theme": "dark", "globalShortcut": "Cmd+K"}))
        setup_cli.write_config(target)
        config = json.loads(target.read_text())
        assert config["theme"] == "dark"
        assert config["globalShortcut"] == "Cmd+K"

    def test_replacing_an_existing_entry_is_reported(self, tmp_path):
        target = tmp_path / "claude_desktop_config.json"
        target.write_text(json.dumps({"mcpServers": {"garmin": {"command": "old"}}}))
        _, replaced = setup_cli.write_config(target)
        assert replaced is True
        assert json.loads(target.read_text())["mcpServers"]["garmin"]["command"] != "old"

    def test_makes_a_backup_before_overwriting(self, tmp_path):
        target = tmp_path / "claude_desktop_config.json"
        target.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
        backup, _ = setup_cli.write_config(target)
        assert backup is not None and backup.exists()
        assert json.loads(backup.read_text())["mcpServers"] == {"other": {"command": "x"}}

    def test_a_corrupt_config_is_replaced_but_backed_up_first(self, tmp_path):
        target = tmp_path / "claude_desktop_config.json"
        target.write_text("{ this is not json")
        backup, _ = setup_cli.write_config(target)
        assert backup is not None and backup.read_text() == "{ this is not json"
        assert "garmin" in json.loads(target.read_text())["mcpServers"]

    def test_a_non_dict_mcpservers_value_is_discarded(self, tmp_path):
        target = tmp_path / "claude_desktop_config.json"
        target.write_text(json.dumps({"mcpServers": ["unexpected"]}))
        setup_cli.write_config(target)
        assert "garmin" in json.loads(target.read_text())["mcpServers"]

    def test_the_command_is_an_absolute_interpreter_path(self, tmp_path):
        # Claude Desktop does not inherit the shell PATH, so a bare name fails.
        target = tmp_path / "claude_desktop_config.json"
        setup_cli.write_config(target)
        command = json.loads(target.read_text())["mcpServers"]["garmin"]["command"]
        assert command.startswith("/")


class TestConfigPath:
    def test_macos_uses_application_support(self, monkeypatch):
        monkeypatch.setattr(setup_cli.platform, "system", lambda: "Darwin")
        assert "Application Support" in str(setup_cli.config_path())
        assert str(setup_cli.config_path()).endswith("claude_desktop_config.json")


class TestLoadConfig:
    def test_missing_file_is_an_empty_config(self, tmp_path):
        assert setup_cli.load_config(tmp_path / "nope.json") == {}

    def test_corrupt_file_is_an_empty_config(self, tmp_path):
        target = tmp_path / "bad.json"
        target.write_text("not json")
        assert setup_cli.load_config(target) == {}


class TestMfaPrompt:
    def test_rejects_an_empty_code_and_asks_again(self, monkeypatch, capsys):
        answers = iter(["", "   ", "483920"])
        monkeypatch.setattr("builtins.input", lambda *a: next(answers))
        assert setup_cli.ask_mfa_code() == "483920"


class TestMainInterruptions:
    def test_ctrl_c_exits_calmly(self, monkeypatch, capsys):
        monkeypatch.setattr(setup_cli, "run", lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
        try:
            setup_cli.main()
        except SystemExit as exit_code:
            assert exit_code.code == 1
        assert "Cancelled" in capsys.readouterr().out

    def test_end_of_input_exits_calmly(self, monkeypatch, capsys):
        monkeypatch.setattr(setup_cli, "run", lambda: (_ for _ in ()).throw(EOFError()))
        try:
            setup_cli.main()
        except SystemExit as exit_code:
            assert exit_code.code == 1
        assert "No input was received" in capsys.readouterr().out
