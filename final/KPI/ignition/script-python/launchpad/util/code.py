def popup(self, viewPath, viewParams = {}, popupTitle = ''):
	"""Open viewPath as a full-screen modal popup below 1000 px viewport width, else a desktop popup."""
	if self.page.props.dimensions.viewport.width < 1000:
		mobilePosition = {"width": "100%", "height": "100%"}
		system.perspective.openPopup(
			'mobile-popup-%s' % str(self.view.params)
			, viewPath
			, params=viewParams
			, title=popupTitle
			, position=mobilePosition
			, showCloseIcon=True
			, resizable=False
			, draggable=False
			, modal=True
			, viewportBound=True
		)
	else:
		system.perspective.openPopup(
			'fullsize-popup-%s' % str(self.view.params)
			, viewPath
			, params=viewParams
			, title=popupTitle
			, showCloseIcon=True
			, resizable=True
			, draggable=True
			, modal=False
			, viewportBound=False
		)