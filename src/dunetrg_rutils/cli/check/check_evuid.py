#!/usr/bin/env python
import pandas as pd
import click


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument('rootfile')
def main(rootfile):

    import ROOT

    es_rdf = ROOT.RDataFrame(
        'triggerAna/event_summary',
        rootfile
        )

    tps_rdf = ROOT.RDataFrame(
        'triggerAna/TriggerPrimitives/tpmakerTPCSimpleThreshold__TriggerPrimitiveMaker',
        rootfile
        )

    print("Loading event summary event_uid")
    es_evuid_df = pd.DataFrame(es_rdf.AsNumpy(columns=["event_uid"]))

    print("Loading tps event_uid")
    tps_evuid_df = pd.DataFrame(tps_rdf.AsNumpy(columns=["event_uid"]))

    # print(es_evuid_df)
    es_event_list = es_evuid_df.event_uid.unique()
    print(es_event_list)

    # print(tps_evuid_df)
    tps_event_list = tps_evuid_df.event_uid.unique()
    print(tps_event_list)

    print(f"Events in EvSum: {len(es_event_list)}")
    print(f"Events in TPs: {len(tps_event_list)}")

if __name__ == '__main__':
    main()
