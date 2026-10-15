#!/usr/bin/env python3
"""Generate a Visual Studio solution with one console project per problem.

Why: a single contest usually ships several problems and every one of them has
its own main(), so they cannot live in one project. This emits a .sln plus one
<Proj>/<Proj>.vcxproj per problem, each compiling a shared source file from the
parent directory.

Two MSVC details are baked in on purpose:

- AdditionalOptions /utf-8: without it, cl.exe run under the default Chinese
  code page 936 emits C4819 and then misparses everything after the first
  non-ASCII byte, producing bogus errors such as "cin is undeclared".
- PlatformToolset v145: matches the toolset shipped with recent Visual Studio
  (check cl.exe version: 14.5x -> v145). Adjust if your install differs.

Usage:
    python tools/make_vs_solution.py --root <contest-dir> --name OJ1234 \
        A:src/A.cpp B:src/B.cpp
"""
import argparse
import os
import uuid

VCXPROJ = """<?xml version="1.0" encoding="utf-8"?>
<Project DefaultTargets="Build" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemGroup Label="ProjectConfigurations">
    <ProjectConfiguration Include="Debug|x64">
      <Configuration>Debug</Configuration>
      <Platform>x64</Platform>
    </ProjectConfiguration>
    <ProjectConfiguration Include="Release|x64">
      <Configuration>Release</Configuration>
      <Platform>x64</Platform>
    </ProjectConfiguration>
  </ItemGroup>
  <PropertyGroup Label="Globals">
    <VCProjectVersion>17.0</VCProjectVersion>
    <ProjectGuid>%(guid)s</ProjectGuid>
    <RootNamespace>%(name)s</RootNamespace>
    <WindowsTargetPlatformVersion>10.0</WindowsTargetPlatformVersion>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props" />
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'" Label="Configuration">
    <ConfigurationType>Application</ConfigurationType>
    <UseDebugLibraries>true</UseDebugLibraries>
    <PlatformToolset>v145</PlatformToolset>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'" Label="Configuration">
    <ConfigurationType>Application</ConfigurationType>
    <UseDebugLibraries>false</UseDebugLibraries>
    <PlatformToolset>v145</PlatformToolset>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.props" />
  <ImportGroup Label="PropertySheets">
    <Import Project="$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props" Condition="exists('$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props')" Label="LocalAppDataPlatform" />
  </ImportGroup>
  <ItemDefinitionGroup>
    <ClCompile>
      <WarningLevel>Level3</WarningLevel>
      <LanguageStandard>stdcpp17</LanguageStandard>
      <AdditionalOptions>/utf-8 %%(AdditionalOptions)</AdditionalOptions>
    </ClCompile>
  </ItemDefinitionGroup>
  <ItemGroup>
    <ClCompile Include="..\\%(src)s" />
  </ItemGroup>
  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.targets" />
</Project>
"""

FILTERS = """<?xml version="1.0" encoding="utf-8"?>
<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemGroup>
    <ClCompile Include="..\\%(src)s">
      <Filter>Source Files</Filter>
    </ClCompile>
  </ItemGroup>
  <ItemGroup>
    <Filter Include="Source Files">
      <UniqueIdentifier>%(fguid)s</UniqueIdentifier>
      <Extensions>cpp;c;cc;cxx</Extensions>
    </Filter>
  </ItemGroup>
</Project>
"""

CPP_GUID = "{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}"


def guid_for(solution, name):
    """Stable GUID so regenerating the solution does not churn the file."""
    return "{" + str(uuid.uuid5(uuid.NAMESPACE_URL, solution + "/" + name)).upper() + "}"


def parse_project(spec):
    """Parse a NAME:SRC spec into (name, source, source_relative_to_project)."""
    if ":" not in spec:
        raise argparse.ArgumentTypeError("expected NAME:SRC, got %r" % spec)
    name, src = spec.split(":", 1)
    name = name.strip()
    src = src.strip().replace("/", os.sep)
    if not name or not src:
        raise argparse.ArgumentTypeError("expected NAME:SRC, got %r" % spec)
    return name, src


def build(root, solution, projects):
    """Write <solution>.sln and one project directory per problem under root."""
    os.makedirs(root, exist_ok=True)
    sln_path = os.path.join(root, solution + ".sln")

    lines = ["",
             "Microsoft Visual Studio Solution File, Format Version 12.00",
             "# Visual Studio Version 17",
             "VisualStudioVersion = 17.0.31903.59",
             "MinimumVisualStudioVersion = 10.0.40219.1"]
    for name, _ in projects:
        g = guid_for(solution, name)
        lines.append('Project("%s") = "%s", "%s\\%s.vcxproj", "%s"'
                     % (CPP_GUID, name, name, name, g))
        lines.append("EndProject")
    lines.append("Global")
    lines.append("\tGlobalSection(SolutionConfigurationPlatforms) = preSolution")
    lines.append("\t\tDebug|x64 = Debug|x64")
    lines.append("\t\tRelease|x64 = Release|x64")
    lines.append("\tEndGlobalSection")
    lines.append("\tGlobalSection(ProjectConfigurationPlatforms) = postSolution")
    for name, _ in projects:
        g = guid_for(solution, name)
        for cfg in ("Debug|x64", "Release|x64"):
            lines.append("\t\t%s.%s.ActiveCfg = %s" % (g, cfg, cfg))
            lines.append("\t\t%s.%s.Build.0 = %s" % (g, cfg, cfg))
    lines.append("\tEndGlobalSection")
    lines.append("\tGlobalSection(ExtensibilityGlobals) = postSolution")
    lines.append("\t\tSolutionGuid = %s" % guid_for(solution, "__solution__"))
    lines.append("\tEndGlobalSection")
    lines.append("EndGlobal")

    with open(sln_path, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")

    for name, src in projects:
        proj_dir = os.path.join(root, name)
        os.makedirs(proj_dir, exist_ok=True)
        ctx = {"guid": guid_for(solution, name), "name": name, "src": src,
               "fguid": guid_for(solution, name + "__filter")}
        with open(os.path.join(proj_dir, name + ".vcxproj"),
                  "w", encoding="utf-8", newline="\r\n") as f:
            f.write(VCXPROJ % ctx)
        with open(os.path.join(proj_dir, name + ".vcxproj.filters"),
                  "w", encoding="utf-8", newline="\r\n") as f:
            f.write(FILTERS % ctx)
    return sln_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", required=True, help="contest working directory")
    parser.add_argument("--name", default="OJ", help="solution base name")
    parser.add_argument("projects", nargs="+", metavar="NAME:SRC",
                        help="one entry per problem, e.g. A:src/A.cpp")
    args = parser.parse_args(argv)
    projects = [parse_project(s) for s in args.projects]
    sln = build(args.root, args.name, projects)
    print("solution : %s" % sln)
    print("projects : %s" % ", ".join(p[0] for p in projects))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
