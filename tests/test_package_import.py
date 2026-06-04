def test_package_exposes_version() -> None:
    import figure_data

    assert isinstance(figure_data.__version__, str)
    assert figure_data.__version__
