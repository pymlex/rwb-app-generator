import hashlib
import json

from generator.reference_data import MAX_FIELDS, profile_data, validate_contract


def write_data(folder, data, name="reference.json"):
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_profile_reports_nested_collections_provider_ids_and_geometry(tmp_path):
    path = write_data(
        tmp_path,
        {
            "payload": {
                "records": [
                    {"externalObjectId": "001", "shape": "LINESTRING(1 2,3 4)", "active": True},
                    {
                        "externalObjectId": "002",
                        "shape": "SRID=4326;MULTILINESTRING((1 2,3 4))",
                        "active": None,
                    },
                ]
            }
        },
        "nested/source.json",
    )
    profile = profile_data(tmp_path)[0]
    assert profile["file"] == "nested/source.json"
    assert profile["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert {"path": '$["payload"]["records"]', "count": 2} in profile["collections"]
    assert profile["geometry_counts"] == {"LINESTRING": 1, "MULTILINESTRING": 1}
    assert profile["external_id_fields"] == ['$["payload"]["records"][]["externalObjectId"]']
    fields = {entry["path"]: entry for entry in profile["fields"]}
    assert fields['$["payload"]["records"][]["active"]']["types"] == ["boolean", "null"]
    assert fields[profile["external_id_fields"][0]]["examples"] == [
        {"value": "001", "truncated": False},
        {"value": "002", "truncated": False},
    ]
    assert "1 2,3 4" not in json.dumps(profile)


def test_profile_caps_metadata_but_scans_all_geometry_values(tmp_path):
    data = {f"field{i:03}": "x" * 200 for i in range(MAX_FIELDS + 8)}
    data["zz_records"] = [{"shape": "POINT EMPTY"}, {"shape": "POLYGON((0 0,1 0,0 0))"}]
    write_data(tmp_path, data)
    profile = profile_data(tmp_path)[0]
    assert len(profile["fields"]) == MAX_FIELDS
    assert profile["omitted_fields"] > 0
    assert profile["omitted_top_keys"] > 0
    example = next(entry for entry in profile["fields"] if entry["path"] == '$["field000"]')[
        "examples"
    ][0]
    assert example == {"value": "x" * 160, "truncated": True}
    assert profile["geometry_counts"] == {"POINT": 1, "POLYGON": 1}
    assert profile_data(tmp_path) == profile_data(tmp_path)


def test_profile_supports_root_arrays_heterogeneous_values_and_empty_folder(tmp_path):
    assert profile_data(tmp_path) == []
    write_data(tmp_path, [1, "label", {"external_id": "original"}, [True, False]])
    profile = profile_data(tmp_path)[0]
    assert profile["root_type"] == "array"
    assert {"path": "$", "count": 4} in profile["collections"]
    assert profile["external_id_fields"] == ['$[]["external_id"]']
    assert profile["geometry_counts"] == {}


def test_contract_rejects_namespace_but_ignores_comments_and_strings():
    assert validate_contract([], "namespace Product; public record Item;", "")
    assert validate_contract([], "namespace Product { public record Item; }", "")
    assert (
        validate_contract(
            [], '// namespace Product;\npublic record Item(string Text = "namespace Product;");', ""
        )
        == []
    )


def test_contract_rejects_polygon_typmod_for_line_only_reference():
    profile = [{"geometry_counts": {"LINESTRING": 50, "MULTILINESTRING": 2}}]
    assert validate_contract(profile, "", "CREATE TABLE areas(shape geometry(Polygon,4326));")
    assert validate_contract(
        profile, "", "CREATE TABLE areas(shape geography(MultiPolygonZ,4326));"
    )
    assert (
        validate_contract(profile, "", "CREATE TABLE areas(shape geometry(Geometry,4326));") == []
    )
    assert (
        validate_contract(profile, "", "CREATE TABLE roads(shape geometry(LineString,4326));") == []
    )
    assert (
        validate_contract(
            profile, "", "-- geometry(Polygon,4326)\nCREATE TABLE records(body jsonb);"
        )
        == []
    )


def test_contract_does_not_invent_geo_or_provider_mapping_requirements():
    nongeo = [{"geometry_counts": {}, "external_id_fields": ['$[]["externalThingId"]']}]
    assert (
        validate_contract(nongeo, "public record Item;", "CREATE TABLE records(body jsonb);") == []
    )
    mixed = [{"geometry_counts": {"LINESTRING": 2, "POLYGON": 1}}]
    assert validate_contract(mixed, "", "CREATE TABLE areas(shape geometry(Polygon,4326));") == []
