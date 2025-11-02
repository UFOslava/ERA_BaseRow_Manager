<?xml version='1.0' encoding='UTF-8'?>
<Project Type="Project" LVVersion="18008000">
	<Item Name="My Computer" Type="My Computer">
		<Property Name="server.app.propertiesEnabled" Type="Bool">true</Property>
		<Property Name="server.control.propertiesEnabled" Type="Bool">true</Property>
		<Property Name="server.tcp.enabled" Type="Bool">false</Property>
		<Property Name="server.tcp.port" Type="Int">0</Property>
		<Property Name="server.tcp.serviceName" Type="Str">My Computer/VI Server</Property>
		<Property Name="server.tcp.serviceName.default" Type="Str">My Computer/VI Server</Property>
		<Property Name="server.vi.callsEnabled" Type="Bool">true</Property>
		<Property Name="server.vi.propertiesEnabled" Type="Bool">true</Property>
		<Property Name="specify.custom.address" Type="Bool">false</Property>
		<Item Name="SubVIs" Type="Folder">
			<Property Name="NI.SortType" Type="Int">3</Property>
			<Item Name="HTTP" Type="Folder">
				<Item Name="Attach Param" Type="Folder">
					<Item Name="Attach Param - Bool.vi" Type="VI" URL="../Attach Param - Bool.vi"/>
					<Item Name="Attach Param - Decimal.vi" Type="VI" URL="../Attach Param - Decimal.vi"/>
					<Item Name="Attach Param - String.vi" Type="VI" URL="../Attach Param - String.vi"/>
					<Item Name="Attach Param.vi" Type="VI" URL="../Attach Param.vi"/>
					<Item Name="Attach Params.vi" Type="VI" URL="../Attach Params.vi"/>
				</Item>
				<Item Name="GET Row.vi" Type="VI" URL="../GET Row.vi"/>
				<Item Name="GET Rows.vi" Type="VI" URL="../GET Rows.vi"/>
				<Item Name="Open Handle.vi" Type="VI" URL="../Open Handle.vi"/>
			</Item>
			<Item Name="JSON Parsing" Type="Folder">
				<Item Name="Generic" Type="Folder">
					<Item Name="Parse Any Cluster.vi" Type="VI" URL="../Parse Any Cluster.vi"/>
					<Item Name="Parse JSON Item.vi" Type="VI" URL="../Parse JSON Item.vi"/>
				</Item>
				<Item Name="Parse BOM Raw Data Array.vi" Type="VI" URL="../Parse BOM Raw Data Array.vi"/>
				<Item Name="Parse BOM Raw Data Row.vi" Type="VI" URL="../Parse BOM Raw Data Row.vi"/>
				<Item Name="Parse Hierarchy Table Row.vi" Type="VI" URL="../Parse Hierarchy Table Row.vi"/>
			</Item>
			<Item Name="[r]GET Decimal Array from Rows.vi" Type="VI" URL="../[r]GET Decimal Array from Rows.vi"/>
			<Item Name="Add BOM Tree Row.vi" Type="VI" URL="../Add BOM Tree Row.vi"/>
			<Item Name="PATCH.vi" Type="VI" URL="../PATCH.vi"/>
			<Item Name="Ping API.vi" Type="VI" URL="../Ping API.vi"/>
			<Item Name="Refresh Hierarchy View.vi" Type="VI" URL="../Refresh Hierarchy View.vi"/>
			<Item Name="Set TreeView Column Width.vi" Type="VI" URL="../Set TreeView Column Width.vi"/>
			<Item Name="Get Item IDs By Filter.vi" Type="VI" URL="../Get Item IDs By Filter.vi"/>
			<Item Name="Main - Handle Heirarchy Drag&amp;Drop.vi" Type="VI" URL="../Main - Handle Heirarchy Drag&amp;Drop.vi"/>
			<Item Name="Refresh Hierarchy View - Populate Table.vi" Type="VI" URL="../Refresh Hierarchy View - Populate Table.vi"/>
			<Item Name="Get Single ID Only By Filter.vi" Type="VI" URL="../Get Single ID Only By Filter.vi"/>
		</Item>
		<Item Name="Tools" Type="Folder">
			<Item Name="Is VI Running Top Level.vi" Type="VI" URL="../Tools/Is VI Running Top Level.vi"/>
			<Item Name="Pretty Print JSON.vi" Type="VI" URL="../Tools/Pretty Print JSON.vi"/>
			<Item Name="Set Panes to Origin.vi" Type="VI" URL="../Tools/Set Panes to Origin.vi"/>
		</Item>
		<Item Name="TypeDef" Type="Folder">
			<Item Name="State Machines" Type="Folder">
				<Item Name="Main - Handle Heirarchy Drag&amp;Drop - States.ctl" Type="VI" URL="../TypeDef/Main - Handle Heirarchy Drag&amp;Drop - States.ctl"/>
				<Item Name="Refresh Hierarchy View - States.ctl" Type="VI" URL="../TypeDef/Refresh Hierarchy View - States.ctl"/>
			</Item>
			<Item Name="BOM Table Raw Items.ctl" Type="VI" URL="../TypeDef/BOM Table Raw Items.ctl"/>
			<Item Name="FIlter.ctl" Type="VI" URL="../TypeDef/FIlter.ctl"/>
			<Item Name="Param.ctl" Type="VI" URL="../TypeDef/Param.ctl"/>
		</Item>
		<Item Name="JSONtext.lvlib" Type="Library" URL="/&lt;vilib&gt;/JDP Science/JSONtext/JSONtext.lvlib"/>
		<Item Name="Main.vi" Type="VI" URL="../Main.vi"/>
		<Item Name="Dependencies" Type="Dependencies">
			<Item Name="user.lib" Type="Folder">
				<Item Name="Array of VData to VArray__ogtk.vi" Type="VI" URL="/&lt;userlib&gt;/_OpenG.lib/lvdata/lvdata.llb/Array of VData to VArray__ogtk.vi"/>
				<Item Name="Build Error Cluster__ogtk.vi" Type="VI" URL="/&lt;userlib&gt;/_OpenG.lib/error/error.llb/Build Error Cluster__ogtk.vi"/>
				<Item Name="Current VIs Parents Ref__ogtk.vi" Type="VI" URL="/&lt;userlib&gt;/_OpenG.lib/appcontrol/appcontrol.llb/Current VIs Parents Ref__ogtk.vi"/>
				<Item Name="Get Header from TD__ogtk.vi" Type="VI" URL="/&lt;userlib&gt;/_OpenG.lib/lvdata/lvdata.llb/Get Header from TD__ogtk.vi"/>
				<Item Name="Get Last PString__ogtk.vi" Type="VI" URL="/&lt;userlib&gt;/_OpenG.lib/lvdata/lvdata.llb/Get Last PString__ogtk.vi"/>
				<Item Name="Get PString__ogtk.vi" Type="VI" URL="/&lt;userlib&gt;/_OpenG.lib/lvdata/lvdata.llb/Get PString__ogtk.vi"/>
				<Item Name="Get TDEnum from Data__ogtk.vi" Type="VI" URL="/&lt;userlib&gt;/_OpenG.lib/lvdata/lvdata.llb/Get TDEnum from Data__ogtk.vi"/>
				<Item Name="Get Variant Attributes__ogtk.vi" Type="VI" URL="/&lt;userlib&gt;/_OpenG.lib/lvdata/lvdata.llb/Get Variant Attributes__ogtk.vi"/>
				<Item Name="MGI Caller&apos;s VI Reference.vi" Type="VI" URL="/&lt;userlib&gt;/_MGI/Application Control/MGI VI Reference/MGI Caller&apos;s VI Reference.vi"/>
				<Item Name="MGI Current VI&apos;s Reference.vi" Type="VI" URL="/&lt;userlib&gt;/_MGI/Application Control/MGI VI Reference/MGI Current VI&apos;s Reference.vi"/>
				<Item Name="MGI Defer Panel Updates.vi" Type="VI" URL="/&lt;userlib&gt;/_MGI/Application Control/MGI Defer Panel Updates.vi"/>
				<Item Name="MGI Get Cluster Elements.vi" Type="VI" URL="/&lt;userlib&gt;/_MGI/Cluster/MGI Get Cluster Elements.vi"/>
				<Item Name="MGI Level&apos;s VI Reference.vi" Type="VI" URL="/&lt;userlib&gt;/_MGI/Application Control/MGI VI Reference/MGI Level&apos;s VI Reference.vi"/>
				<Item Name="MGI Replace Cluster Element.vi" Type="VI" URL="/&lt;userlib&gt;/_MGI/Cluster/MGI Replace Cluster Element.vi"/>
				<Item Name="MGI Top Level VI Reference.vi" Type="VI" URL="/&lt;userlib&gt;/_MGI/Application Control/MGI VI Reference/MGI Top Level VI Reference.vi"/>
				<Item Name="MGI VI Reference.vi" Type="VI" URL="/&lt;userlib&gt;/_MGI/Application Control/MGI VI Reference.vi"/>
				<Item Name="Set Data Name__ogtk.vi" Type="VI" URL="/&lt;userlib&gt;/_OpenG.lib/lvdata/lvdata.llb/Set Data Name__ogtk.vi"/>
				<Item Name="Type Descriptor Enumeration__ogtk.ctl" Type="VI" URL="/&lt;userlib&gt;/_OpenG.lib/lvdata/lvdata.llb/Type Descriptor Enumeration__ogtk.ctl"/>
				<Item Name="Type Descriptor Header__ogtk.ctl" Type="VI" URL="/&lt;userlib&gt;/_OpenG.lib/lvdata/lvdata.llb/Type Descriptor Header__ogtk.ctl"/>
				<Item Name="Type Descriptor__ogtk.ctl" Type="VI" URL="/&lt;userlib&gt;/_OpenG.lib/lvdata/lvdata.llb/Type Descriptor__ogtk.ctl"/>
				<Item Name="Variant to Header Info__ogtk.vi" Type="VI" URL="/&lt;userlib&gt;/_OpenG.lib/lvdata/lvdata.llb/Variant to Header Info__ogtk.vi"/>
			</Item>
			<Item Name="vi.lib" Type="Folder">
				<Item Name="Base64 Support.lvlib" Type="Library" URL="/&lt;vilib&gt;/JDP Science/JDP Science Common Utilities/Base64/Base64 Support.lvlib"/>
				<Item Name="Check if File or Folder Exists.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/libraryn.llb/Check if File or Folder Exists.vi"/>
				<Item Name="Error Cluster From Error Code.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/error.llb/Error Cluster From Error Code.vi"/>
				<Item Name="Get LV Class Name.vi" Type="VI" URL="/&lt;vilib&gt;/Utility/LVClass/Get LV Class Name.vi"/>
				<Item Name="Get Text Rect.vi" Type="VI" URL="/&lt;vilib&gt;/picture/picture.llb/Get Text Rect.vi"/>
				<Item Name="GPError.lvlib" Type="Library" URL="/&lt;vilib&gt;/GPower/Error/GPError.lvlib"/>
				<Item Name="JDP Timestamp.lvlib" Type="Library" URL="/&lt;vilib&gt;/JDP Science/JDP Science Common Utilities/Timestamp/JDP Timestamp.lvlib"/>
				<Item Name="JDP Utility.lvlib" Type="Library" URL="/&lt;vilib&gt;/JDP Science/JDP Science Common Utilities/JDP Utility.lvlib"/>
				<Item Name="JSONtext LVClass Serializer.lvclass" Type="LVClass" URL="/&lt;vilib&gt;/JDP Science/JSONtext/LVClass Serializer/JSONtext LVClass Serializer.lvclass"/>
				<Item Name="LabVIEWHTTPClient.lvlib" Type="Library" URL="/&lt;vilib&gt;/httpClient/LabVIEWHTTPClient.lvlib"/>
				<Item Name="LVNumericRepresentation.ctl" Type="VI" URL="/&lt;vilib&gt;/numeric/LVNumericRepresentation.ctl"/>
				<Item Name="LVPointTypeDef.ctl" Type="VI" URL="/&lt;vilib&gt;/Utility/miscctls.llb/LVPointTypeDef.ctl"/>
				<Item Name="NI_Data Type.lvlib" Type="Library" URL="/&lt;vilib&gt;/Utility/Data Type/NI_Data Type.lvlib"/>
				<Item Name="NI_FileType.lvlib" Type="Library" URL="/&lt;vilib&gt;/Utility/lvfile.llb/NI_FileType.lvlib"/>
				<Item Name="NI_PackedLibraryUtility.lvlib" Type="Library" URL="/&lt;vilib&gt;/Utility/LVLibp/NI_PackedLibraryUtility.lvlib"/>
				<Item Name="Path To Command Line String.vi" Type="VI" URL="/&lt;vilib&gt;/AdvancedString/Path To Command Line String.vi"/>
				<Item Name="PathToUNIXPathString.vi" Type="VI" URL="/&lt;vilib&gt;/Platform/CFURL.llb/PathToUNIXPathString.vi"/>
				<Item Name="VariantType.lvlib" Type="Library" URL="/&lt;vilib&gt;/Utility/VariantDataType/VariantType.lvlib"/>
			</Item>
		</Item>
		<Item Name="Build Specifications" Type="Build"/>
	</Item>
</Project>
