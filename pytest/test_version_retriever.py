from nddaqconf.core.conf_utils import get_version, nightly_or_release, release_or_dev, get_rte_script


# How do I get rid all the fixtures and pytest_generate_tests??
def test_nightly_or_release():
    releases = {
        'N22-12-12'         : 'nightly', 
        'NT2222-12-12'      : 'nothing', 
        'NT22-1222-12'      : 'nothing', 
        'NT22-12-4012'      : 'nothing', 
        'NT22-12-12'        : 'nightly', 
        'NE22-12-12'        : 'nightly', 
        'NS22-12-12'        : 'nightly', 
        'dunedaq-v4.6.3'    : 'rel',     
        'dunedaq11-v4.6.3'  : 'nothing', 
        'dunedaq-4.6.3'     : 'nothing', 
        'dunedaq-v4.6.3-cs8': 'rel',     
        'dunedaq-v4.6.3-rc3': 'rel',     
    }
    import os

    for rel, rn in releases.items():
        os.environ["DUNE_DAQ_BASE_RELEASE"] = rel
        
        print(f'\n\nTesting nightly_or_release({rel})')
        nor = nightly_or_release(rel)
        if   rn == 'nothing' and nor == None:
            print('pass')
        elif rn == nor:
            print('pass')
        else:
            print(f'FAIL ({nor}, should be {rn})')


if __name__ == "__main__":
    test_nightly_or_release()
