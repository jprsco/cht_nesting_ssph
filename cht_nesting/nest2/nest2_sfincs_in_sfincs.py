"""
Nest 2 script for nesting a hydromt_sfincs SfincsModel within another SfincsModel.

Reads water level time series from the overall SfincsModel's ``sfincs_his.nc``
output and sets them as water level boundary conditions on the detail SfincsModel.
Station names in the his-file are stored as fixed-length bytes by the SFINCS
Fortran kernel and are decoded automatically.
"""

# import os
# from typing import Any, List, Optional, Union

# import numpy as np
# import pandas as pd
# import xarray as xr
# from cht_tide.tide_predict import predict
# from cht_utils.fileio.deltares_ini import IniStruct
# from cht_utils.physics.waves import split_waves_guza


# def nest2_sfincs_in_sfincs(
#     overall: Any,
#     detail: Any,
#     obs_point_prefix: Optional[str] = None,
#     output_path: Optional[str] = None,
#     output_file: Optional[str] = None,
#     boundary_water_level_correction: float = 0.0,
#     return_maximum: bool = False,
#     filter_incoming: bool = False,
#     bc_path: Optional[str] = None,
#     **kwargs: Any,
# ) -> Union[Any, pd.Series]:
#     """Nest a hydromt_sfincs SfincsModel within another hydromt_sfincs SfincsModel.

#     Reads water level time series (``point_zs``) from the overall model's
#     ``sfincs_his.nc`` output and applies them as water level boundary conditions
#     on the detail SfincsModel via ``detail.water_level.set_timeseries()``.

#     An optional incoming-wave filter (Guza method) can be applied using the
#     velocity and bed-level variables also present in the his-file.

#     Parameters
#     ----------
#     overall : hydromt_sfincs.SfincsModel
#         The coarse SfincsModel whose ``sfincs_his.nc`` is read.
#     detail : hydromt_sfincs.SfincsModel
#         The fine SfincsModel that receives the water level boundary conditions.
#     obs_point_prefix : str, optional
#         Prefix prepended to each detail boundary point name when looking up
#         stations in the overall his-file.  Defaults to ``detail.name``.
#     output_path : str, optional
#         Directory containing the overall model's output files.  Defaults to
#         ``str(overall.root.path)``.
#     output_file : str, optional
#         Name of the SFINCS his output file.  Defaults to ``"sfincs_his.nc"``.
#     boundary_water_level_correction : float, optional
#         Uniform offset (metres) added to every boundary time series.  Useful
#         for datum corrections.  Defaults to ``0.0``.
#     return_maximum : bool, optional
#         When ``True``, return a :class:`~pandas.Series` of peak (maximum)
#         water levels across all boundary points instead of the BC component.
#         Defaults to ``False``.
#     filter_incoming : bool, optional
#         When ``True``, apply the Guza incoming-wave filter to isolate the
#         incident wave component from ``point_zs``.  Requires ``point_u``,
#         ``point_v``, and ``point_zb`` to be present in the his-file.
#         Defaults to ``False``.
#     bc_path : str, optional
#         If provided, write the boundary conditions to disk by calling
#         ``detail.water_level.write()`` after setting.  The value of *bc_path*
#         is not used directly — writing goes to the model's configured root.
#     **kwargs : Any
#         Extra keyword arguments are accepted and silently ignored so that the
#         function can be called uniformly through the :func:`nest2` dispatcher.

#     Returns
#     -------
#     hydromt_sfincs water_level component or pandas.Series
#         The ``detail.water_level`` component (default) or, when
#         *return_maximum* is ``True``, a :class:`~pandas.Series` with the
#         peak water level for each time step across all boundary points.

#     Raises
#     ------
#     ValueError
#         If a required observation point name is not found among the stations
#         in the overall his-file.
#     """
#     if not output_path:
#         output_path = str(overall.root.path)
#     if not obs_point_prefix:
#         obs_point_prefix = detail.name
#     if not output_file:
#         output_file = "sfincs_his.nc"

#     # The name is the index with 4 leading zeros
#     point_names: List[str] = [
#         f"{obs_point_prefix}_{str(ind + 1).zfill(4)}"
#         for ind, _row in detail.water_level.gdf.iterrows()
#     ]

#     # Open the overall his-file and decode station names (bytes or str).
#     fn_his: str = os.path.join(output_path, output_file)
#     ds = xr.open_dataset(fn_his)
#     all_stations: List[str] = [
#         s.decode("utf-8").strip()
#         if isinstance(s, (bytes, np.bytes_))
#         else str(s).strip()
#         for s in ds["station_name"].values
#     ]

#     # Map each required point name to a station index (case-insensitive).
#     ireq: List[int] = []
#     for pname in point_names:
#         matched = False
#         for ist, st in enumerate(all_stations):
#             if pname.lower() == st.lower():
#                 ireq.append(ist)
#                 matched = True
#                 break
#         if not matched:
#             raise ValueError(
#                 f"Observation point '{pname}' not found in '{fn_his}'. "
#                 f"Available stations: {all_stations}"
#             )

#     times = pd.DatetimeIndex(ds["time"].values)
#     bzs = pd.DataFrame(ds["point_zs"].values[:, ireq], index=times)

#     # Optional Guza incoming-wave filter: isolates the incident component.
#     if filter_incoming:
#         bzu = pd.DataFrame(ds["point_u"].values[:, ireq], index=times)
#         bzv = pd.DataFrame(ds["point_v"].values[:, ireq], index=times)
#         bzb: np.ndarray = ds["point_zb"].values[
#             0, ireq
#         ]  # bed levels are time-invariant

#         for icol in range(len(ireq)):
#             df_col = pd.DataFrame(
#                 {
#                     "time": times,
#                     "z": bzs.iloc[:, icol].values,
#                     "u": bzu.iloc[:, icol].values,
#                     "v": bzv.iloc[:, icol].values,
#                 }
#             )
#             df_col = split_waves_guza(df_col, float(bzb[icol]))
#             bzs.iloc[:, icol] = df_col["zin"].values

#     ds.close()

#     # Astronomic correction from an optional .cor file.
#     vcor: Union[float, pd.Series] = 0.0
#     corfile: Optional[str] = detail.config.get("corfile")
#     if corfile:
#         vcor = get_vcor(os.path.join(str(detail.root.path), corfile), times)

#     # Build the BC DataFrame: integer GDF-index columns matched to time index.
#     df_bcs = pd.DataFrame(index=times)
#     for icol, (ind, _row) in enumerate(detail.water_level.gdf.iterrows()):
#         df_bcs[ind] = bzs.iloc[:, icol].values + boundary_water_level_correction + vcor

#     detail.water_level.set_timeseries(df_bcs)

#     if bc_path is not None:
#         detail.water_level.write()

#     if return_maximum:
#         return (bzs + boundary_water_level_correction + vcor).max(axis=1)
#     return detail.water_level


# def get_vcor(corfile: str, times: pd.DatetimeIndex) -> pd.Series:
#     """Compute an astronomic water level correction from a ``.cor`` file.

#     Parameters
#     ----------
#     corfile : str
#         Path to the ``.cor`` file (Deltares INI format) containing tidal
#         component amplitudes and phases.
#     times : pandas.DatetimeIndex
#         Time axis for which to evaluate the tidal prediction.

#     Returns
#     -------
#     pandas.Series
#         Predicted astronomic water levels at each time in *times*.
#     """
#     d = IniStruct(filename=corfile)
#     astro = d.section[0].data
#     names: List[str] = []
#     amp: List[float] = []
#     phi: List[float] = []
#     for icmp, cmp in enumerate(astro.index):
#         names.append(cmp)
#         amp.append(astro[1][icmp])
#         phi.append(astro[2][icmp])
#     df = pd.DataFrame(
#         {"amplitude": pd.Series(amp), "phase": pd.Series(phi)},
#         index=pd.Series(names, name="component"),
#     )
#     return predict(df, times)


import os
import pandas as pd
from typing import Optional, Any
from cht_utils.deltares_ini import IniStruct
from cht_tide.tide_predict import predict
from cht_utils.physics.waves import split_waves_guza

def nest2_sfincs_in_sfincs(overall: Any,
                           detail: Any,
                           obs_point_prefix: Optional[str] = None,
                           output_path: Optional[str] = None,
                           output_file: Optional[str] = None,
                           boundary_water_level_correction: float = 0.0,
                           return_maximum: bool = False,
                           filter_incoming: bool = False,
                           bc_path: Optional[str] = None,
                           **kwargs) -> Any:
    """
    Nest a SFINCS model within another SFINCS model.

    Parameters:
    overall (Any): The overall SFINCS model.
    detail (Any): The detailed SFINCS model.
    obs_point_prefix (Optional[str]): The prefix for observation points. Default is None.
    output_path (Optional[str]): The path to the output files. Default is None.
    output_file (Optional[str]): The name of the output file. Default is None.
    boundary_water_level_correction (float): The correction to apply to the boundary water levels. Default is 0.0.
    return_maximum (bool): Whether to return the maximum values. Default is False.
    filter_incoming (bool): Whether to filter incoming data. Default is False.
    bc_path (Optional[str]): The path to the boundary conditions files. Default is None.
    **kwargs: Additional keyword arguments.

    Returns:
    Any: The boundary conditions or maximum values.
    """
    if not output_path:
        # Path of the overall output time series
        output_path = overall.path

    if not obs_point_prefix:
        # Name of obs points
        obs_point_prefix = detail.name

    if overall.input.variables.outputformat[0:3] == "bin":
        # ascii output
        if not output_file:
            output_file = "zst.txt"
    else:
        # netcdf
        if not output_file:
            output_file = "sfincs_his.nc"

    point_names = []
    # Loop through gdf of boundary conditions
    for ind, point in detail.boundary_conditions.gdf.iterrows():
        point_names.append(obs_point_prefix + "_" + point["name"])
    zstfile = os.path.join(output_path, output_file)

    # Return DataFrame bzs
    bzs = overall.output.read_his_file(station=point_names,
                                       parameter="zs",
                                       file_name=zstfile)
    ts = bzs.index

    # Check if filtering is needed
    if filter_incoming:
        # Read velocities
        bzu = overall.output.read_his_file(station=point_names,
                                           parameter="point_u",
                                           file_name=zstfile)
        bzv = overall.output.read_his_file(station=point_names,
                                           parameter="point_v",
                                           file_name=zstfile)

        # Read bed levels
        bzb = overall.output.read_his_file(station=point_names,
                                           parameter="zb",
                                           file_name=zstfile)

        # Loop over all points
        for icol, point in detail.boundary_conditions.gdf.iterrows():
            # Make new DataFrame with water level and velocity time series for this point
            df = pd.DataFrame()
            df["time"] = ts
            df["z"] = bzs.iloc[:, icol].values
            df["u"] = bzu.iloc[:, icol].values
            df["v"] = bzv.iloc[:, icol].values
            # Get the bed level at this point
            zb = bzb.iloc[0, icol]
            # Filter out the outgoing waves
            df = split_waves_guza(df, zb)
            # Update water levels in bzs
            bzs.iloc[:, icol] = df["zin"].values

    # Astro correction
    vcor = 0.0
    if detail.input.variables.corfile:
        vcor = get_vcor(os.path.join(detail.path, detail.input.variables.corfile), ts)

    for icol, point in detail.boundary_conditions.gdf.iterrows():
        df = pd.DataFrame()
        df["time"] = ts
        df["wl"] = bzs.iloc[:, icol].values + boundary_water_level_correction + vcor
        df = df.set_index("time")
        detail.boundary_conditions.gdf.at[icol, "timeseries"] = df

    # Write bzs file
    if bc_path is not None:
        detail.boundary_conditions.write_boundary_conditions_timeseries()

    # zs_maximum for clustering
    if return_maximum:
        zmax = -999.0
        for icol, point in detail.boundary_conditions.gdf.iterrows():
            zx = point.data.max()
            if zx > zmax:
                zs = point.data
                zmax = zx
        return zs
    else:
        return detail.boundary_conditions


def get_vcor(corfile: str, times: pd.DatetimeIndex) -> pd.Series:
    """
    Add astronomic correction to time series.

    Parameters:
    corfile (str): The path to the correction file.
    times (pd.DatetimeIndex): The time series.

    Returns:
    pd.Series: The astronomic correction.
    """
    # Read cor file
    d = IniStruct(filename=corfile)
    astro = d.section[0].data
    names = []
    amp = []
    phi = []
    for icmp, cmp in enumerate(astro.index):
        names.append(cmp)
        amp.append(astro[1][icmp])
        phi.append(astro[2][icmp])
    df = pd.DataFrame()
    df["component"] = pd.Series(names)
    df["amplitude"] = pd.Series(amp)
    df["phase"] = pd.Series(phi)
    df = df.set_index("component")
    return predict(df, times)
