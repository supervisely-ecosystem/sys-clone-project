# TEMPORARY test image: latest hardened base + the unreleased mesh SDK branch.
# Once the mesh changes are released, drop this image and point config.json's
# docker_image back.
FROM supervisely/base-py-sdk-hardened:6.73.580

# The pinned source package reads RELEASE_VERSION first; set it to bypass the
# setup.py path that shells out to `git` (git is absent in the hardened base).
RUN RELEASE_VERSION="0.0.0+ffbd303" \
    python3 -m pip install --no-cache-dir --force-reinstall --no-deps \
    "https://github.com/supervisely/supervisely/archive/ffbd303962b17f986aeda7503ebff7169459a1fd.tar.gz"
