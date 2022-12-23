# adsyncd
Azure AD Synchronization Daemon

Will automatically create or delete users with their respective Microsoft 365 handles.
This distribution is only intended for internal use at the xpertnova GmbH, Hamburg.
This software is not to be licensed publicly. All rights reserved.

Usage:
	adsync start - Starts daemon
	adsync stop - Stops daemon
	adsync sync - Triggers sync
	
Config file in /var/adsyncd/config.cfg
It contains various examples and instructions on how to configure the software
	
Ships with a debian .deb package in dist/

All components under the lib/ folder are subject to their respective licenses. Thereby, copying and/or modification may not be subject to the copyright of the other software components.
