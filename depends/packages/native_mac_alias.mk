package=native_mac_alias
$(package)_version=2.2.0
$(package)_download_path=https://github.com/dmgbuild/mac_alias/archive/
$(package)_file_name=v$($(package)_version).tar.gz
$(package)_sha256_hash=421e6d7586d1f155c7db3e7da01ca0dacc9649a509a253ad7077b70174426499
$(package)_install_libdir=$(build_prefix)/lib/python3/dist-packages

# Pure Python, used by contrib/macdeploy/macdeployqtplus; copied as is.
define $(package)_stage_cmds
    mkdir -p $($(package)_staging_dir)$($(package)_install_libdir) && \
    cp -r mac_alias $($(package)_staging_dir)$($(package)_install_libdir)/
endef
